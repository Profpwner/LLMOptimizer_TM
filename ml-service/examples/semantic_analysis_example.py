"""
Example: Using the Semantic Saturation Engine

This script demonstrates how to use the ML service's semantic saturation
capabilities for content analysis and optimization.
"""

import asyncio
import httpx
import json
from typing import List, Dict, Any


# Configuration
API_BASE_URL = "http://localhost:8000"
API_KEY = "your-api-key-here"  # Replace with actual API key


async def perform_semantic_analysis(content_items: List[Dict[str, Any]]):
    """
    Perform comprehensive semantic analysis on content items
    """
    async with httpx.AsyncClient() as client:
        # Prepare request
        request_data = {
            "content_items": content_items,
            "target_keywords": [
                "artificial intelligence",
                "machine learning",
                "deep learning",
                "neural networks",
                "data science"
            ],
            "reference_topics": [
                "supervised learning",
                "unsupervised learning",
                "reinforcement learning",
                "natural language processing",
                "computer vision"
            ],
            "optimization_goals": ["seo", "readability", "engagement"]
        }
        
        # Send request
        response = await client.post(
            f"{API_BASE_URL}/semantic-analysis",
            json=request_data,
            headers={"Authorization": f"Bearer {API_KEY}"}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None


async def generate_embeddings(texts: List[str]):
    """
    Generate embeddings for text snippets
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/embeddings/generate",
            json={
                "texts": texts,
                "model_type": "default"
            },
            headers={"Authorization": f"Bearer {API_KEY}"}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None


async def similarity_search(query: str, corpus: List[str]):
    """
    Perform similarity search in a corpus
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/similarity/search",
            json={
                "query": query,
                "corpus": corpus,
                "top_k": 5
            },
            headers={"Authorization": f"Bearer {API_KEY}"}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None


def print_analysis_results(results: Dict[str, Any]):
    """
    Pretty print analysis results
    """
    print("\n=== SEMANTIC ANALYSIS RESULTS ===\n")
    
    # Metrics
    print("📊 Metrics:")
    metrics = results.get("metrics", {})
    print(f"  • Semantic Health Score: {metrics.get('semantic_health_score', 0):.2%}")
    print(f"  • Content Density: {metrics.get('content_density', 0):.3f}")
    print(f"  • Average Gap Severity: {metrics.get('avg_gap_severity', 0):.2%}")
    print(f"  • Critical Gaps: {metrics.get('critical_gaps', 0)}")
    
    # Content Mesh
    print("\n🕸️  Content Mesh:")
    mesh = results.get("content_mesh", {})
    print(f"  • Nodes: {mesh.get('nodes', 0)}")
    print(f"  • Edges: {mesh.get('edges', 0)}")
    print(f"  • Communities: {mesh.get('communities', 0)}")
    print(f"  • Density: {mesh.get('density', 0):.3f}")
    
    # Semantic Gaps
    print("\n🔍 Top Semantic Gaps:")
    gaps = results.get("semantic_gaps", [])[:3]
    for i, gap in enumerate(gaps, 1):
        print(f"  {i}. {gap.get('description', 'Unknown gap')}")
        print(f"     Severity: {gap.get('severity', 0):.2%}")
        print(f"     Type: {gap.get('type', 'unknown')}")
    
    # Optimization Suggestions
    print("\n💡 Top Optimization Suggestions:")
    suggestions = results.get("optimization_suggestions", [])[:5]
    for i, sugg in enumerate(suggestions, 1):
        print(f"  {i}. [{sugg.get('priority', 'medium').upper()}] {sugg.get('description', 'Unknown suggestion')}")
        print(f"     Category: {sugg.get('category', 'unknown')}")
        print(f"     Implementation: {sugg.get('implementation', 'No details')[:100]}...")
    
    print(f"\n⏱️  Processing Time: {results.get('processing_time', 0):.2f} seconds")


async def main():
    """
    Main example workflow
    """
    print("🚀 Semantic Saturation Engine Example\n")
    
    # Sample content for analysis
    content_items = [
        {
            "id": "article_1",
            "title": "Introduction to Machine Learning",
            "content": """
            Machine learning is a revolutionary field of artificial intelligence that enables computers 
            to learn and improve from experience without being explicitly programmed. This technology 
            has transformed industries ranging from healthcare to finance, making it one of the most 
            sought-after skills in today's job market.
            
            At its core, machine learning involves algorithms that can identify patterns in data and 
            make decisions with minimal human intervention. These algorithms improve their performance 
            over time as they are exposed to more data, making them increasingly accurate and efficient.
            """,
            "metadata": {
                "author": "AI Expert",
                "category": "AI Fundamentals",
                "published_date": "2024-01-15"
            }
        },
        {
            "id": "article_2",
            "title": "Deep Learning and Neural Networks",
            "content": """
            Deep learning represents a subset of machine learning that's inspired by the structure 
            and function of the human brain. Using artificial neural networks with multiple layers, 
            deep learning models can automatically learn hierarchical representations of data.
            
            These models have achieved remarkable success in tasks such as image recognition, 
            natural language processing, and speech recognition. The key advantage of deep learning 
            is its ability to automatically extract features from raw data, eliminating the need 
            for manual feature engineering.
            """,
            "metadata": {
                "author": "Neural Network Researcher",
                "category": "Advanced AI",
                "published_date": "2024-01-16"
            }
        },
        {
            "id": "article_3",
            "title": "Practical Applications of AI in Business",
            "content": """
            Artificial intelligence is no longer a futuristic concept but a practical tool that 
            businesses use daily to gain competitive advantages. From chatbots that provide 24/7 
            customer service to predictive analytics that forecast market trends, AI applications 
            are diverse and impactful.
            
            Companies are leveraging AI for automated decision-making, personalized marketing, 
            fraud detection, and supply chain optimization. The key to successful AI implementation 
            lies in understanding both the capabilities and limitations of these technologies.
            """,
            "metadata": {
                "author": "Business Analyst",
                "category": "AI Applications",
                "published_date": "2024-01-17"
            }
        }
    ]
    
    # 1. Perform Semantic Analysis
    print("1️⃣  Performing semantic analysis...")
    analysis_results = await perform_semantic_analysis(content_items)
    
    if analysis_results:
        print_analysis_results(analysis_results)
        
        # Save visualization data
        with open("semantic_analysis_visualization.json", "w") as f:
            json.dump(analysis_results.get("visualizations", {}), f, indent=2)
        print("\n📁 Visualization data saved to 'semantic_analysis_visualization.json'")
    
    # 2. Generate Embeddings Example
    print("\n2️⃣  Generating embeddings for key phrases...")
    key_phrases = [
        "machine learning algorithms",
        "deep neural networks",
        "artificial intelligence applications",
        "data science techniques",
        "computer vision models"
    ]
    
    embeddings_result = await generate_embeddings(key_phrases)
    if embeddings_result:
        print(f"  ✓ Generated {embeddings_result['count']} embeddings")
        print(f"  ✓ Embedding dimensions: {embeddings_result['dimensions']}")
    
    # 3. Similarity Search Example
    print("\n3️⃣  Performing similarity search...")
    search_query = "How does deep learning work with neural networks?"
    corpus = [
        "Deep learning uses neural networks with multiple layers",
        "Machine learning is a subset of artificial intelligence",
        "Neural networks are inspired by the human brain",
        "Data science involves analyzing large datasets",
        "Computer vision enables machines to interpret images"
    ]
    
    search_results = await similarity_search(search_query, corpus)
    if search_results:
        print(f"  Query: '{search_query}'")
        print("  Top matches:")
        for i, result in enumerate(search_results['results'], 1):
            print(f"    {i}. [{result['score']:.3f}] {result['text']}")
    
    print("\n✅ Example completed!")


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())