import re
from dataclasses import dataclass, field 
from ai_gateway_redteam.common.errors import InvalidCaseError

PLACEHOLDER = re.compile(r"\{[a-z_]+\}")

@dataclass(frozen=True)
class Target:
    """The system under test. Comes from command line, never from case files"""

    gateway_url: str
    model_host: str
    api_key: str | None = field(default = None, repr = False)

def fill_placeholders(text: str, target: Target) -> str:
    """Replace {target} and {model_host}; fail if any placeholder is left unfilled"""
    text = replace_target(text, target)
    text = replace_model_host(text, target)
    placeholders = PLACEHOLDER.findall(text)
    if placeholders:
        raise InvalidCaseError(f"The case target: {text} has placeholders other than target and model_host. These are : {placeholders}")
    return text

def replace_target(text:str, target: Target) -> str:
    return text.replace("{target}", target.gateway_url)

def replace_model_host(text:str, target: Target) -> str:
    return text.replace("{model_host}", target.model_host)
