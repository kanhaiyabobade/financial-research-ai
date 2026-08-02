import os
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def generate_red_flags(text: str) -> str:
    """
    Analyze a DRHP and identify important investment risks.
    """

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""
You are a professional IPO risk analyst.

Read the following Draft Red Herring Prospectus (DRHP).

Identify all major investment risks.

For each risk provide:

1. Risk Title
2. Risk Description
3. Risk Level (High / Medium / Low)

Focus on:

- Legal issues
- Pending litigation
- High debt
- Continuous losses
- Negative cash flow
- Customer concentration
- Regulatory issues
- Promoter concerns
- Industry risks
- Competition
- Corporate governance
- Dependency on suppliers

Return the answer in markdown format.

DRHP:

{text[:25000]}
"""

        response = model.generate_content(prompt)

        return response.text

    except Exception as e:
        return f"Error generating red flags: {e}"