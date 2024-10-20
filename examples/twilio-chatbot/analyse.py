import os
import json
from textblob import TextBlob
from collections import Counter
import re

def load_transcript(file_path):
    with open(file_path, 'r') as file:
        return file.read()

def analyze_sentiment(text):
    blob = TextBlob(text)
    return blob.sentiment.polarity

def calculate_satisfaction_score(sentiment_score, keyword_count):
    # Normalize sentiment score to 0-100 range
    normalized_sentiment = (sentiment_score + 1) * 50
    
    # Calculate keyword score (0-100)
    max_keywords = 10  # Adjust this based on your expectations
    keyword_score = min(keyword_count / max_keywords * 100, 100)
    
    # Combine sentiment and keyword scores (equal weight)
    satisfaction_score = (normalized_sentiment + keyword_score) / 2
    
    return round(satisfaction_score, 2)

def count_keywords(text):
    positive_keywords = ['thank', 'appreciate', 'great', 'excellent', 'helpful', 'satisfied']
    negative_keywords = ['frustrated', 'angry', 'disappointed', 'unhappy', 'problem', 'issue']
    
    word_count = Counter(re.findall(r'\w+', text.lower()))
    
    positive_count = sum(word_count[word] for word in positive_keywords)
    negative_count = sum(word_count[word] for word in negative_keywords)
    
    return positive_count - negative_count

def analyze_call(transcript_path):
    transcript = load_transcript(transcript_path)
    
    sentiment_score = analyze_sentiment(transcript)
    keyword_count = count_keywords(transcript)
    satisfaction_score = calculate_satisfaction_score(sentiment_score, keyword_count)
    
    analysis = {
        "sentiment_score": round(sentiment_score, 2),
        "keyword_count": keyword_count,
        "satisfaction_score": satisfaction_score
    }
    
    return analysis

def main():
    transcript_path = "call_transcript.txt"  # Update this with the actual path to your transcript file
    
    if not os.path.exists(transcript_path):
        print(f"Error: Transcript file not found at {transcript_path}")
        return
    
    analysis = analyze_call(transcript_path)
    
    print("Call Analysis:")
    print(f"Sentiment Score: {analysis['sentiment_score']}")
    print(f"Keyword Count: {analysis['keyword_count']}")
    print(f"Satisfaction Score: {analysis['satisfaction_score']}")
    
    # Optionally, save the analysis to a JSON file
    with open("call_analysis.json", "w") as f:
        json.dump(analysis, f, indent=2)
    print("Analysis saved to call_analysis.json")

if __name__ == "__main__":
    main()
