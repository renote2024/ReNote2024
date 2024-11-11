"""
This module is used to chat with the local LLM Llama3 model.
"""

import ollama

def localChat(msg):
  response = ollama.chat(
      model='llama3',
      messages=[{'role': 'user', 'content': msg}]
  )

  return response['message']['content']
