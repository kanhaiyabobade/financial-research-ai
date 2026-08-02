import os
import re
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure the Gemini API key
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def generate_summary(text: str) -> str:
    """
    Generates a structured executive summary of the DRHP document using Gemini.
    """
    if not api_key:
        return "Gemini API key is not configured. Please add GEMINI_API_KEY to your .env file."
    
    try:
        # Use gemini-1.5-flash for fast and cost-effective text generation
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            "You are an expert equity research analyst. Analyze the following Draft Red Herring Prospectus (DRHP) "
            "text and generate a comprehensive, structured summary. Highlight the company's business model, "
            "industry position, financial performance, and key purposes of the IPO. Use bullet points and clear headings. "
            "Format the output in markdown:\n\n"
            f"{text[:40000]}"  # Safe character limit for prompt context
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating summary: {str(e)}"

def generate_red_flags(text: str) -> str:
    """
    Identifies regulatory, legal, and operational risk factors (red flags) in the DRHP using Gemini.
    """
    if not api_key:
        return "Gemini API key is not configured. Please add GEMINI_API_KEY to your .env file."
        
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            "You are a forensic auditor and risk management expert. Analyze the following Draft Red Herring Prospectus (DRHP) "
            "text and identify key investment risks, litigation issues, outstanding regulatory concerns, promoters' history, "
            "and other potential red flags that prospective investors should know. Use clear bullet points. "
            "Format the output in markdown:\n\n"
            f"{text[:40000]}"
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating red flags: {str(e)}"

def generate_ipo_score(text: str) -> float:
    """
    Evaluates the IPO metrics and returns a numeric score between 0 and 100.
    """
    if not api_key:
        return 50.0
        
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            "Analyze the following Draft Red Herring Prospectus (DRHP) text and evaluate the investment quality of this IPO. "
            "Provide a single numeric score between 0 and 100 representing the strength of the investment (where 0 is extremely risky/poor and 100 is excellent/safe). "
            "Respond ONLY with the number (e.g. 78.5 or 65) and nothing else:\n\n"
            f"{text[:40000]}"
        )
        response = model.generate_content(prompt)
        
        # Parse the float score from the response
        match = re.search(r"\d+(\.\d+)?", response.text.strip())
        if match:
            return float(match.group(0))
        return 50.0
    except Exception:
        return 50.0

def generate_recommendation(text: str) -> str:
    """
    Generates a final investment decision recommendation (INVEST, WATCH, or AVOID) with rationale.
    """
    if not api_key:
        return "Gemini API key is not configured. Please add GEMINI_API_KEY to your .env file."
        
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            "You are a senior investment committee director. Based on the following Draft Red Herring Prospectus (DRHP) text, "
            "provide your final investment recommendation. You MUST choose one of the following words as the prefix: "
            "'INVEST', 'WATCH', or 'AVOID', followed by a concise, professional explanation justifying your decision. "
            "Format the output in markdown:\n\n"
            f"{text[:40000]}"
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating recommendation: {str(e)}"
