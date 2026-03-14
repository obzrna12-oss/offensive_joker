from flask import Flask, request, jsonify
from llama_cpp import Llama
import threading

app = Flask(__name__)

#MODEL_PATH = "jackiebot.4.2Q6_K.gguf"
MODEL_PATH = "Jackie_5.4_8b.Q8_0.gguf"
llm = Llama(model_path=MODEL_PATH, n_threads=8, n_ctx=256, verbose=False)
lock = threading.Lock()


@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    prompt = data.get('prompt')
    max_tokens = data.get('max_tokens', 256)
    temperature = data.get('temperature', 0.9)
#old stop stop=['"', '\n', '}', 'Instruction:', 'input:']
    with lock:
        output = llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=0.9,
            repeat_penalty=1.1,
            stop=['"',  '}', 'Instruction:', 'input:']

        )

    response = output['choices'][0]['text'].strip()
    return jsonify({'response': response})


if __name__ == '__main__':
    print("LLM Service starting...")
    app.run(host='localhost', port=5000, threaded=False)