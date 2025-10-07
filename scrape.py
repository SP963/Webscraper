from bs4 import BeautifulSoup


def extract_body_content(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    body_content = soup.body
    return str(body_content) if body_content else html_content


def clean_body_content(body_content):
    soup = BeautifulSoup(body_content, "html.parser")

    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()

    text = soup.get_text(separator="\n")
    cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return cleaned


def split_dom_content(text, max_length=6000):
    return [text[i : i + max_length] for i in range(0, len(text), max_length)]
