import json

def test_parsing():
    raw_content = '{"response": null, "snippets": null}'
    response_json = json.loads(raw_content)
    answer = response_json.get("response") or ""
    snippets_dict = response_json.get("snippets") or {}
    
    print(f"answer type: {type(answer)}")
    print(f"snippets_dict type: {type(snippets_dict)}")
test_parsing()
