import os
import json
import urllib.request
import requests
from dotenv import load_dotenv

load_dotenv()

def call_deepseek(prompt):
    """
    工具：调用Deepseek大模型
    入参：prompt(给大模型的提示词)
    出参:大模型生成的文本
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return"❌ 错误：未在 .env 文件中找到 DEEPSEEK_API_KEY"
    url = "https://api.deepseek.com/chat/completions"
    hd = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    data = {
        "model":"deepseek-chat",
        "messages":[
            {"role":"system","content":"你是一个资深的餐饮数据分析师，擅长撰写专业的经营周报"},
            {"role":"user","content":prompt}
        ],
        "temperature":0.5
    }
    try:
        res = requests.post(url,headers=hd,json=data,timeout=60)
        res.raise_for_status()

        result_json = res.json()
        reply_text = result_json["choices"][0]["message"]["content"]
        return reply_text
    except requests.exceptions.Timeout:
        return "❌ 大模型调用超时（超过60秒），请稍后重试。"
    except Exception as e:
        return f"❌ 大模型调用失败：{e}"

