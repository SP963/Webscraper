# LLM integration utilities
import os
import logging
import requests
import json
from openai import OpenAI

logger = logging.getLogger("playwright_tutorial")

# Determine which provider to use based on environment variables
# Currently supports Groq (default) and OpenAI (if OPENAI_API_KEY is set)


def _get_provider():
    # Return the provider name if an API key is present, otherwise return None.
    # This allows the caller to handle the missing‑key situation gracefully.
    # Prioritize a custom vLLM endpoint if configured.
    if os.getenv("VLLM_BASE_URL"):
        return "vllm"
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    return None


def _call_groq_api(prompt: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "openai/gpt-oss-20b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 2048,
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def _call_vllm_api(prompt: str) -> str:
    """Call a local vLLM server using the OpenAI compatible client.

    The endpoint URL and model are taken from environment variables to match the
    example in `test.py`:
        VLLM_BASE_URL – e.g., "http://192.168.0.200:8010/v1"
        VLLM_MODEL   – e.g., "Qwen/Qwen3-14B"
    If not provided, defaults are used.
    """
    base_url = os.getenv("VLLM_BASE_URL")
    if not base_url:
        raise RuntimeError("VLLM_BASE_URL not set for vLLM provider")
    model = os.getenv("VLLM_MODEL", "Qwen/Qwen3-14B")
    # vLLM does not require a real API key; we can pass a placeholder.
    client = OpenAI(api_key="EMPTY", base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=2048,
    )
    return response.choices[0].message.content.strip()


def clean_content_via_llm(raw_content: str) -> str:
    """Send the scraped raw content to an LLM and get a cleaned, concise version.

    The prompt asks the model to read the entire scraped data and return only the meaningful textual information,
    removing navigation, boilerplate, and any leftover HTML artifacts.
    """
    provider = _get_provider()
    # If no provider (no API key), skip LLM processing and return the raw content.
    if not provider:
        logger.warning(
            "No LLM API key configured – returning raw content without LLM cleaning."
        )
        return raw_content

    # prompt = (
    #     "You are given raw scraped text from a website. Extract only the meaningful, human‑readable content, "
    #     "removing navigation menus, footers, ads, code snippets, and any duplicate or irrelevant information. "
    #     "Return the cleaned text preserving paragraph structure.\n\n"
    #     f"---\n{raw_content}\n---"
    # )
    prompt = (
        "You are given raw scraped text from a website. Carefully read and understand the entire content. "
        "Your task is to extract only the meaningful, human-readable information intended for users. This includes:\n"
        "- Articles, blog posts, product descriptions, guides, or documentation\n"
        "- Relevant code snippets that are part of the content (e.g., examples, tutorials)\n\n"
        "Remove all unrelated or structural elements, such as:\n"
        "- Navigation menus, headers, footers\n"
        "- Advertisements, cookie notices, and subscription pop-ups\n"
        "- Repeated links, category listings, or boilerplate\n"
        "- Inline scripts, layout HTML, or other non-content elements\n\n"
        "Preserve the structure of the original content, including paragraph breaks, section titles, and properly formatted code blocks.\n\n"
        "Here is the raw content:\n"
        f"---\n{raw_content}\n---"
    )
    try:
        if provider == "groq":
            return _call_groq_api(prompt)
        elif provider == "vllm":
            return _call_vllm_api(prompt)
    except Exception as e:
        logger.error(f"LLM cleaning failed: {e}")
        raise


def chunk_content_via_llm(text: str) -> list:
    """Ask the LLM to split the cleaned text into meaningful chunks.

    The LLM is prompted to return a JSON array where each element is a chunk of
    text that represents a logical section (e.g., a heading and its related
    paragraph). If the LLM response cannot be parsed, the function falls back to
    a simple word‑based split.
    """
    provider = _get_provider()
    if not provider:
        logger.warning("No LLM API key configured – falling back to simple split.")
        # Simple fallback: split by double newlines
        return [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]

    # prompt = (
    #     "You are given a long piece of cleaned text from a website. Split it into "
    #     "meaningful sections, preserving headings and related paragraphs. Return the "
    #     "result as a JSON array of strings, where each string is a chunk. Do not add any "
    #     "explanations or extra characters.\n\n"
    #     f"---\n{text}\n---"
    # )
    prompt = (
        "You are given a cleaned piece of technical documentation text. "
        "Your task is to split it into meaningful and complete chunks based on topics or sections. "
        "Each chunk should include related content under a single concept or heading. "
        "You MUST preserve section headings, descriptive text, code snippets, notes, and tables together "
        "if they belong to the same topic.\n\n"
        "Output the result as a JSON array of strings. Each string must be a self‑contained section.\n\n"
        "For example, if a heading is followed by an explanation, a code snippet, and an output table, all of that should remain in one chunk.\n\n"
        "Do not split logical sections across chunks. Do not add explanations or extra characters.\n\n"
        "---\n" + text + "\n---"
    )
    try:
        if provider == "groq":
            response = _call_groq_api(prompt)
        elif provider == "vllm":
            response = _call_vllm_api(prompt)
        # Clean possible markdown code fences and whitespace
        cleaned = response.strip()
        if cleaned.startswith("```"):
            # Remove leading/trailing backticks and optional language specifier
            cleaned = cleaned.strip("`")
            # If there is a language specifier after the first three backticks, drop the first line
            lines = cleaned.splitlines()
            if lines and not lines[0].strip().startswith("["):
                cleaned = "\n".join(lines[1:])
        # The response should be a JSON array string
        # Attempt to locate a JSON array within the response
        start_idx = cleaned.find("[")
        end_idx = cleaned.rfind("]")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = cleaned[start_idx : end_idx + 1]
        else:
            json_str = cleaned
        # Ensure proper double‑quotes for JSON parsing
        json_str = json_str.replace("'", '"')
        # Remove stray newlines inside strings (they are already split by chunks)
        try:
            chunks = json.loads(json_str)
        except Exception as parse_err:
            logger.error(f"Failed JSON parse for LLM chunking: {parse_err}")
            # Fallback to simple split by double newlines
            return [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
        if isinstance(chunks, list):
            return chunks
        else:
            raise ValueError("LLM did not return a JSON list")
    except Exception as e:
        logger.error(f"LLM chunking failed: {e}")
        # Fallback to simple split by double newlines
        return [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
