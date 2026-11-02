import base64
import json
import re
from typing import Any
from urllib.parse import unquote

# The search of a TestOps test-cases link, up to the end of the URL in a `<url|label>` link.
TEST_CASES_SEARCH = re.compile(r"(/test-cases\?search=)([^|>]+)")


def post_text(post: dict[str, Any]) -> str:
    """The blocks of a Block Kit post as the lines a person reads in Slack: a `mrkdwn` section
    as its text, a divider as `---`. The search of a TestOps test-cases link is decoded into
    its AQL. Any other block fails: the Conclusion posts no other."""
    lines = []
    for block in post["blocks"]:
        if block == {"type": "divider"}:
            lines.append("---")
        elif block["type"] == "section" and block["text"]["type"] == "mrkdwn":
            lines.append(TEST_CASES_SEARCH.sub(decoded_search, block["text"]["text"]))
        else:
            raise ValueError(f"Not a block of a Conclusion: {block}")
    return "\n".join(lines)


def decoded_search(link: re.Match[str]) -> str:
    """The AQL of a test-cases search: one filter of the `aql` kind, as JSON in base64."""
    search = json.loads(base64.b64decode(unquote(link[2])))
    match search:
        case [{"id": "aql", "type": "string", "value": str(aql)}]:
            return f"{link[1]}{aql}"
    raise ValueError(f"Not an AQL search: {search}")
