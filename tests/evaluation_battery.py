import os
import time
import json
import random
import requests
from datetime import datetime
from dotenv import load_dotenv

from api.config import get_settings, get_azure_openai_client

load_dotenv()

# Configuration
LEGISTAR_MATTERS_URL = "https://webapi.legistar.com/v1/mwdh2o/Matters"
RAG_API_URL = "http://localhost:8000/chat"
NUM_QUESTIONS = 50
REPORT_PATH = os.path.join(os.path.dirname(__file__), "validation_report.md")

def fetch_legistar_pool() -> list[dict]:
    """Fetch a pool of matters from Legistar to select from."""
    print("Fetching pool of matters from Legistar API...")
    matters = []
    # Fetch top 500 to have a good pool
    params = {"$top": 500, "$orderby": "MatterIntroDate desc"}
    try:
        response = requests.get(LEGISTAR_MATTERS_URL, params=params)
        response.raise_for_status()
        matters = response.json()
        print(f"Successfully fetched {len(matters)} matters.")
    except Exception as e:
        print(f"Failed to fetch matters from Legistar: {e}")
    return matters

def generate_qa_pair(matter: dict, client, settings) -> dict:
    """Use the LLM to generate a realistic user question and expected answer based on a matter."""
    title = matter.get("MatterTitle", "Unknown Title")
    status = matter.get("MatterStatusName", "Unknown Status")
    date = matter.get("MatterIntroDate", "Unknown Date")
    matter_id = matter.get("MatterId", "Unknown ID")

    system_prompt = """You are an expert data generator.
Given the details of a municipal board matter, formulate a realistic, natural-language question a citizen or board member might ask about this specific matter.
Also, formulate the ideal concise factual answer based STRICTLY on the provided details.
You MUST respond with valid JSON in the exact structure below:
{
    "question": "The question...?",
    "expected_answer": "The factual answer based only on the details provided..."
}
"""
    user_prompt = f"Matter Title: {title}\nMatter Date: {date}\nMatter Status: {status}\nMatter ID: {matter_id}"

    for attempt in range(3):
        try:
            # We use the configured chat model, e.g., o3-mini or gpt-4o
            # For o3-mini JSON mode isn't formally supported to same extent as 4o but strict prompting works well,
            # but to be safe we'll use regular parsing.
            response = client.chat.completions.create(
                model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            content = response.choices[0].message.content.strip()
            # Clean up markdown code blocks if the model wrapped it
            if content.startswith("```json"):
                 content = content[7:]
            if content.startswith("```"):
                 content = content[3:]
            if content.endswith("```"):
                 content = content[:-3]
                 
            return json.loads(content.strip())
        except Exception as e:
            print(f"Failed to generate QA pair (attempt {attempt+1}): {e}")
            time.sleep(2)
            
    return {"question": "", "expected_answer": ""}

def query_rag_system(question: str) -> dict:
    """Submit the question to the local RAG backend and get the response."""
    try:
        response = requests.post(RAG_API_URL, json={"query": question, "history": []})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error querying RAG system: {e}")
        return {"response": "Error reaching RAG system", "citations": []}

def judge_response(question: str, expected_answer: str, actual_answer: str, client, settings) -> dict:
    """Use LLM-as-a-judge to grade the actual answer against the expected answer on a 0-5 scale."""
    system_prompt = """You are an strict and objective evaluator grading a Search/RAG agent's response accuracy.
You will be given a Question, an Expected Answer, and the Actual Answer provided by the agent.
You must assign a score from 0 to 5 based on how well the Actual Answer matches the facts of the Expected Answer and addresses the Question.
- 5: Perfectly accurate and complete.
- 3-4: Mostly accurate, but missing minor details or containing slight hallucinations.
- 1-2: Barely addresses the question, highly inaccurate, or hallucinates significantly.
- 0: Completely wrong, refuses to answer, or misses the core fact entirely.

You MUST respond with valid JSON in the exact structure below:
{
    "score": 5,
    "reasoning": "Brief explanation of why this score was given..."
}
"""
    user_prompt = f"Question: {question}\nExpected Answer: {expected_answer}\nActual Answer: {actual_answer}"

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            content = response.choices[0].message.content.strip()
            
            # Clean up markdown code blocks
            if content.startswith("```json"):
                 content = content[7:]
            if content.startswith("```"):
                 content = content[3:]
            if content.endswith("```"):
                 content = content[:-3]
                 
            return json.loads(content.strip())
        except Exception as e:
            print(f"Failed to judge response (attempt {attempt+1}): {e}")
            time.sleep(2)
            
    return {"score": 0, "reasoning": "Failed to evaluate due to API error."}

def generate_markdown_report(results: list[dict], total_score: int, max_possible: int, avg_score: float):
    """Write the results to a markdown report."""
    print(f"Writing report to {REPORT_PATH}...")
    
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# RAG System Automated QA Validation Report\n\n")
        f.write(f"**Date Run:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Total Score:** {total_score} / {max_possible}\n")
        f.write(f"**Average Score:** {avg_score:.2f} / 5.0\n\n")
        f.write("---\n\n")
        
        for i, res in enumerate(results, 1):
            f.write(f"## Test {i} (Score: {res['score']}/5)\n\n")
            f.write(f"**Matter Title Source:** {res['matter_title']}\n\n")
            f.write(f"**Question:** {res['question']}\n\n")
            f.write(f"**Expected Answer:** {res['expected_answer']}\n\n")
            f.write(f"**RAG Actual Answer:** {res['actual_answer']}\n\n")
            f.write(f"> **Judge Reasoning:** {res['reasoning']}\n\n")
            f.write("---\n\n")

def run_battery():
    print(f"Starting Validation Battery for {NUM_QUESTIONS} questions...")
    settings = get_settings()
    client = get_azure_openai_client()
    
    pool = fetch_legistar_pool()
    if not pool:
        print("Cannot proceed without Legistar matters.")
        return
        
    random.shuffle(pool)
    selected_matters = pool[:NUM_QUESTIONS]
    
    results = []
    total_score = 0
    
    for i, matter in enumerate(selected_matters, 1):
        print(f"\n[{i}/{NUM_QUESTIONS}] Processing Matter: {matter.get('MatterTitle', '')[:60]}...")
        
        # 1. Generate Q/A Pair
        qa_pair = generate_qa_pair(matter, client, settings)
        question = qa_pair.get("question")
        expected = qa_pair.get("expected_answer")
        
        if not question:
            print(f"[{i}/{NUM_QUESTIONS}] Skiping: Failed to generate question.")
            continue
            
        print(f"  Q: {question}")
        
        # 2. Query RAG
        rag_response = query_rag_system(question)
        actual_answer = rag_response.get("response", "No answer")
        
        # 3. Judge Response
        judgment = judge_response(question, expected, actual_answer, client, settings)
        score = int(judgment.get("score", 0))
        reasoning = judgment.get("reasoning", "No reasoning provided.")
        
        print(f"  Score: {score}/5")
        
        # 4. Record
        total_score += score
        results.append({
            "matter_title": matter.get("MatterTitle", "Unknown Title"),
            "question": question,
            "expected_answer": expected,
            "actual_answer": actual_answer,
            "score": score,
            "reasoning": reasoning
        })
        
    # 5. Output Report
    max_possible = len(results) * 5
    avg_score = total_score / len(results) if results else 0
    
    generate_markdown_report(results, total_score, max_possible, avg_score)
    print(f"\nBattery Complete. Total Score: {total_score}/{max_possible} ({avg_score:.2f} avg). Report saved to {REPORT_PATH}")

if __name__ == "__main__":
    run_battery()
