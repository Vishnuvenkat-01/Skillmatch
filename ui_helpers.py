"""
ui_helpers.py
=============
Pure utility functions shared across the CareerMatch AI UI.
No Streamlit calls, no session-state access, no service calls.
"""


def format_section_as_text(items, section_type: str = "general") -> str:
    """
    Format a list of dicts or strings into clean, human-readable markdown text.
    Replaces raw JSON displays for Education, Experience, and Projects.

    Args:
        items: A list of strings or dicts, or a single string/non-list value.
        section_type: One of "education", "experience", "projects", or "general".

    Returns:
        A markdown-formatted string. Returns "*None listed*" for empty inputs.
    """
    if not items:
        return "*None listed*"

    if isinstance(items, str):
        return items.strip() or "*None listed*"

    if not isinstance(items, list):
        return str(items)

    formatted_blocks = []
    for item in items:
        if isinstance(item, str):
            formatted_blocks.append(f"• {item}")
        elif isinstance(item, dict):
            if section_type == "education":
                degree      = item.get("degree")      or item.get("title")  or item.get("field")       or ""
                institution = item.get("institution") or item.get("university") or item.get("school")  or ""
                year        = item.get("year")        or item.get("dates")  or item.get("duration")    or ""

                parts = []
                if degree:      parts.append(f"**{degree}**")
                if institution: parts.append(f"*{institution}*")
                if year:        parts.append(f"({year})")

                line = (
                    " - ".join(parts)
                    if parts
                    else ", ".join(
                        f"{k.replace('_', ' ').title()}: {v}" for k, v in item.items() if v
                    )
                )
                formatted_blocks.append(f"• {line}")

            elif section_type == "experience":
                title    = item.get("title")    or item.get("role")         or item.get("position")     or ""
                company  = item.get("company")  or item.get("organization") or ""
                duration = item.get("duration") or item.get("dates")        or item.get("year")         or ""
                desc     = item.get("description") or item.get("responsibilities") or ""

                header_parts = []
                if title:    header_parts.append(f"**{title}**")
                if company:  header_parts.append(f"*{company}*")
                if duration: header_parts.append(f"({duration})")

                header = (
                    " | ".join(header_parts)
                    if header_parts
                    else ", ".join(
                        f"{k.replace('_', ' ').title()}: {v}"
                        for k, v in item.items()
                        if k != "description" and v
                    )
                )
                block = f"• {header}"
                if desc:
                    if isinstance(desc, list):
                        for d in desc:
                            block += f"\n  - {d}"
                    else:
                        block += f"\n  - {desc}"
                formatted_blocks.append(block)

            elif section_type == "projects":
                name = item.get("name")  or item.get("title") or ""
                desc = item.get("description") or item.get("summary") or ""
                tech = (
                    item.get("tech_stack")
                    or item.get("technologies")
                    or item.get("skills")
                    or ""
                )

                parts = []
                if name: parts.append(f"**{name}**")

                header = (
                    " ".join(parts)
                    if parts
                    else ", ".join(
                        f"{k.replace('_', ' ').title()}: {v}"
                        for k, v in item.items()
                        if k != "description" and v
                    )
                )
                block = f"• {header}"
                if desc:
                    block += f"\n  - {desc}"
                if tech:
                    tech_str = ", ".join(tech) if isinstance(tech, list) else str(tech)
                    block += f"\n  - *Tech:* {tech_str}"
                formatted_blocks.append(block)

            else:
                fields = [
                    f"**{k.replace('_', ' ').title()}:** {v}"
                    for k, v in item.items() if v
                ]
                formatted_blocks.append("• " + " | ".join(fields))
        else:
            formatted_blocks.append(f"• {str(item)}")

    return "\n\n".join(formatted_blocks)
