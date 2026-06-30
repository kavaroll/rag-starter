from openai import OpenAI

from app.config import VLLM_URL, LLM_MODEL


class LLM:

    def __init__(self):
        self.model = LLM_MODEL
        self.client = OpenAI(
            api_key="EMPTY",
            base_url=f"{VLLM_URL}/v1",
        )

    def generate(self, prompt):
        return self.chat([{"role": "user", "content": prompt}]).content

    def chat(self, messages, tools=None):
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 1024,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
        }
        if tools:
            kwargs["tools"] = tools
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message
