import openai
from langsmith import wrappers, traceable

# Auto-trace LLM calls in-context
client = wrappers.wrap_openai(openai.Client())


@traceable  # Auto-trace this function
def pipeline(user_input: str):
    result = client.chat.completions.create(
        messages=[{"role": "user", "content": user_input}], model="gpt-4o-mini"
    )
    return result.choices[0].message.content


pipeline("Hello, world!")
# Out:  Hello there! How can I assist you today?
