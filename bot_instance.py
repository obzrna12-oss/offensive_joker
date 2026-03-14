import requests

LLM_SERVICE_URL = "http://localhost:5000/generate"

def generate_with_service(prompt, max_tokens=250, temperature=0.85):
    try:
        response = requests.post(LLM_SERVICE_URL, json={
            'prompt': prompt,
            'max_tokens': max_tokens,
            'temperature': temperature
        }, timeout=60)
        if response.status_code == 200:
            return response.json()['response']
        else:
            print(f"Service error: {response.status_code}")
            return None
    except Exception as e:
        print(f"Service call failed: {e}")
        return None