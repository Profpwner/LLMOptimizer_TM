"""
Content analysis and processing tasks for workflows.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio

from celery import Task
from celery_app import app

from src.content.analysis import ContentAnalyzer, ContentType


logger = logging.getLogger(__name__)


class ContentTask(Task):
    """Base class for content tasks with shared functionality."""
    
    def __init__(self):
        super().__init__()
        self._content_analyzer = None
    
    @property
    def content_analyzer(self):
        if self._content_analyzer is None:
            self._content_analyzer = ContentAnalyzer()
        return self._content_analyzer


@app.task(base=ContentTask, bind=True, name='content_optimization.tasks.analyze_content')
def analyze_content(
    self,
    workflow_instance_id: str,
    step_id: str,
    input_data: Dict[str, Any],
    context: Dict[str, Any],
    step_results: Dict[str, Any],
    analysis_type: str = "comprehensive",
    **kwargs
) -> Dict[str, Any]:
    """
    Analyze content using the content analysis engine.
    
    Args:
        workflow_instance_id: ID of the workflow instance
        step_id: ID of the current step
        input_data: Input data from workflow
        context: Workflow context
        step_results: Previous step results
        analysis_type: Type of analysis to perform
    
    Returns:
        Analysis results and updated context
    """
    try:
        # Extract content from input
        content_id = input_data.get('content_id')
        content = input_data.get('content', '')
        content_type = input_data.get('content_type', ContentType.TEXT)
        
        # Get analysis options
        options = {
            'title': input_data.get('title', ''),
            'meta_description': input_data.get('meta_description', ''),
            'keywords': input_data.get('keywords', []),
            'target_audience': input_data.get('target_audience'),
            'language': input_data.get('language')
        }
        
        # Run analysis asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        analysis_result = loop.run_until_complete(
            self.content_analyzer.analyze(
                content_id=content_id,
                content=content,
                content_type=content_type,
                options=options
            )
        )
        
        # Convert to dict for serialization
        result_dict = analysis_result.dict()
        
        # Update context with key metrics
        context_update = {
            'content_analyzed': True,
            'analysis_timestamp': datetime.utcnow().isoformat(),
            'quality_score': analysis_result.quality_score.overall_score if analysis_result.quality_score else 0,
            'seo_score': analysis_result.seo_analysis.overall_score if analysis_result.seo_analysis else 0,
            'readability_grade': (
                analysis_result.text_analysis.readability.average_grade_level 
                if analysis_result.text_analysis else 0
            )
        }
        
        return {
            'status': 'completed',
            'analysis': result_dict,
            'issues_found': len(analysis_result.issues),
            'recommendations_count': len(analysis_result.recommendations),
            'context': context_update,
            'output': {
                'analysis_result': result_dict,
                'summary': analysis_result.summary
            }
        }
        
    except Exception as e:
        logger.error(f"Content analysis failed: {e}")
        raise


@app.task(base=ContentTask, bind=True, name='content_optimization.tasks.extract_keywords')
def extract_keywords(
    self,
    workflow_instance_id: str,
    step_id: str,
    input_data: Dict[str, Any],
    context: Dict[str, Any],
    step_results: Dict[str, Any],
    **kwargs
) -> Dict[str, Any]:
    """
    Extract keywords from content.
    
    Returns:
        Extracted keywords and phrases
    """
    try:
        # Get content from previous analysis or input
        if 'analyze_content' in step_results:
            content = step_results['analyze_content']['analysis']['text_analysis']['content']
            keywords_data = step_results['analyze_content']['analysis']['text_analysis']['keywords']
        else:
            content = input_data.get('content', '')
            # Run keyword extraction
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            from src.content.analysis.text_analyzer import TextAnalyzer
            analyzer = TextAnalyzer()
            
            analysis = loop.run_until_complete(
                analyzer.analyze(content)
            )
            keywords_data = analysis.keywords.dict()
        
        # Extract top keywords and phrases
        top_keywords = keywords_data.get('top_words', [])[:10]
        key_phrases = keywords_data.get('key_phrases', [])[:10]
        all_keywords = [kw['keyword'] for kw in keywords_data.get('keywords', [])][:20]
        
        return {
            'status': 'completed',
            'keywords': {
                'top_words': top_keywords,
                'key_phrases': key_phrases,
                'all_keywords': all_keywords,
                'keyword_count': len(all_keywords)
            },
            'context': {
                'keywords_extracted': True,
                'primary_keywords': top_keywords[:5]
            },
            'output': {
                'keywords': all_keywords,
                'phrases': key_phrases
            }
        }
        
    except Exception as e:
        logger.error(f"Keyword extraction failed: {e}")
        raise


@app.task(base=ContentTask, bind=True, name='content_optimization.tasks.check_grammar')
def check_grammar(
    self,
    workflow_instance_id: str,
    step_id: str,
    input_data: Dict[str, Any],
    context: Dict[str, Any],
    step_results: Dict[str, Any],
    **kwargs
) -> Dict[str, Any]:
    """
    Check content for grammar and spelling errors.
    
    Returns:
        Grammar check results
    """
    try:
        # Get content
        content = input_data.get('content', '')
        
        # Simple grammar check (in production, use LanguageTool or similar)
        issues = []
        suggestions = []
        
        # Basic checks
        common_errors = {
            'teh': 'the',
            'recieve': 'receive',
            'occured': 'occurred',
            'seperate': 'separate',
            'definately': 'definitely'
        }
        
        words = content.lower().split()
        for i, word in enumerate(words):
            if word in common_errors:
                issues.append({
                    'type': 'spelling',
                    'position': i,
                    'error': word,
                    'suggestion': common_errors[word]
                })
                suggestions.append(f"Replace '{word}' with '{common_errors[word]}'")
        
        # Check for basic grammar patterns
        if '  ' in content:
            issues.append({
                'type': 'spacing',
                'error': 'double_space',
                'suggestion': 'Remove extra spaces'
            })
        
        grammar_score = max(0, 100 - len(issues) * 10)
        
        return {
            'status': 'completed',
            'grammar_check': {
                'score': grammar_score,
                'issues_count': len(issues),
                'issues': issues,
                'suggestions': suggestions
            },
            'context': {
                'grammar_checked': True,
                'grammar_score': grammar_score,
                'has_grammar_issues': len(issues) > 0
            },
            'output': {
                'grammar_score': grammar_score,
                'corrections_needed': len(issues)
            }
        }
        
    except Exception as e:
        logger.error(f"Grammar check failed: {e}")
        raise


@app.task(base=ContentTask, bind=True, name='content_optimization.tasks.analyze_readability')
def analyze_readability(
    self,
    workflow_instance_id: str,
    step_id: str,
    input_data: Dict[str, Any],
    context: Dict[str, Any],
    step_results: Dict[str, Any],
    **kwargs
) -> Dict[str, Any]:
    """
    Analyze content readability.
    
    Returns:
        Readability analysis results
    """
    try:
        # Get content and target audience
        content = input_data.get('content', '')
        target_audience = input_data.get('target_audience', 'general')
        
        # Run readability analysis
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        from src.content.analysis.text_analyzer import TextAnalyzer
        analyzer = TextAnalyzer()
        
        analysis = loop.run_until_complete(
            analyzer.analyze(content, target_audience=target_audience)
        )
        
        readability = analysis.readability
        
        # Determine if readability matches target audience
        target_grades = {
            'children': (3, 6),
            'teens': (7, 10),
            'general': (8, 12),
            'professional': (12, 16),
            'academic': (14, 18)
        }
        
        min_grade, max_grade = target_grades.get(target_audience, (8, 12))
        grade = readability.average_grade_level
        
        is_appropriate = min_grade <= grade <= max_grade
        
        recommendations = []
        if grade < min_grade:
            recommendations.append(f"Content is too simple for {target_audience} audience")
        elif grade > max_grade:
            recommendations.append(f"Content is too complex for {target_audience} audience")
        
        return {
            'status': 'completed',
            'readability': {
                'flesch_reading_ease': readability.flesch_reading_ease,
                'grade_level': grade,
                'target_appropriate': is_appropriate,
                'recommendations': recommendations
            },
            'context': {
                'readability_analyzed': True,
                'readability_grade': grade,
                'readability_appropriate': is_appropriate
            },
            'output': {
                'grade_level': grade,
                'reading_ease': readability.flesch_reading_ease,
                'is_appropriate': is_appropriate
            }
        }
        
    except Exception as e:
        logger.error(f"Readability analysis failed: {e}")
        raise


@app.task(base=ContentTask, bind=True, name='content_optimization.tasks.fact_check')
def fact_check(
    self,
    workflow_instance_id: str,
    step_id: str,
    input_data: Dict[str, Any],
    context: Dict[str, Any],
    step_results: Dict[str, Any],
    **kwargs
) -> Dict[str, Any]:
    """
    Perform basic fact checking on content.
    
    Returns:
        Fact checking results
    """
    try:
        content = input_data.get('content', '')
        
        # Mock fact checking (in production, integrate with fact-checking APIs)
        facts_to_verify = []
        verified_facts = []
        disputed_facts = []
        
        # Look for claims with numbers, dates, or statistics
        import re
        
        # Find statistical claims
        stat_pattern = r'\d+(?:\.\d+)?%|\d+(?:,\d{3})*(?:\.\d+)?'
        statistics = re.findall(stat_pattern, content)
        
        for stat in statistics:
            facts_to_verify.append({
                'type': 'statistic',
                'claim': stat,
                'context': 'Statistical claim found in content'
            })
        
        # Find date claims
        date_pattern = r'\b(?:19|20)\d{2}\b|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b'
        dates = re.findall(date_pattern, content)
        
        for date in dates:
            facts_to_verify.append({
                'type': 'date',
                'claim': date,
                'context': 'Date reference found in content'
            })
        
        # Mock verification (in production, use real fact-checking)
        confidence_score = 85 if len(facts_to_verify) < 5 else 75
        
        return {
            'status': 'completed',
            'fact_check': {
                'facts_found': len(facts_to_verify),
                'facts_verified': len(verified_facts),
                'facts_disputed': len(disputed_facts),
                'confidence_score': confidence_score,
                'facts_to_verify': facts_to_verify[:10]  # Limit to 10
            },
            'context': {
                'fact_checked': True,
                'factual_confidence': confidence_score,
                'requires_verification': len(facts_to_verify) > 0
            },
            'output': {
                'confidence_score': confidence_score,
                'verification_needed': len(facts_to_verify)
            }
        }
        
    except Exception as e:
        logger.error(f"Fact checking failed: {e}")
        raise


@app.task(base=ContentTask, bind=True, name='content_optimization.tasks.check_plagiarism')
def check_plagiarism(
    self,
    workflow_instance_id: str,
    step_id: str,
    input_data: Dict[str, Any],
    context: Dict[str, Any],
    step_results: Dict[str, Any],
    **kwargs
) -> Dict[str, Any]:
    """
    Check content for plagiarism.
    
    Returns:
        Plagiarism check results
    """
    try:
        content = input_data.get('content', '')
        
        # Mock plagiarism check (in production, use Copyscape API or similar)
        # For demo, we'll simulate by checking content length and complexity
        word_count = len(content.split())
        
        # Simulate originality score
        if word_count < 100:
            originality_score = 95
        elif word_count < 500:
            originality_score = 90
        else:
            originality_score = 85
        
        # Mock similar sources
        similar_sources = []
        if originality_score < 90:
            similar_sources.append({
                'url': 'https://example.com/similar-article',
                'similarity': 100 - originality_score,
                'matched_text': 'Sample matched text...'
            })
        
        return {
            'status': 'completed',
            'plagiarism_check': {
                'originality_score': originality_score,
                'is_original': originality_score >= 80,
                'similar_sources_count': len(similar_sources),
                'similar_sources': similar_sources
            },
            'context': {
                'plagiarism_checked': True,
                'originality_score': originality_score,
                'is_original': originality_score >= 80
            },
            'output': {
                'originality_score': originality_score,
                'passed': originality_score >= 80
            }
        }
        
    except Exception as e:
        logger.error(f"Plagiarism check failed: {e}")
        raise


@app.task(base=ContentTask, bind=True, name='content_optimization.tasks.generate_quality_report')
def generate_quality_report(
    self,
    workflow_instance_id: str,
    step_id: str,
    input_data: Dict[str, Any],
    context: Dict[str, Any],
    step_results: Dict[str, Any],
    **kwargs
) -> Dict[str, Any]:
    """
    Generate comprehensive quality report from all checks.
    
    Returns:
        Comprehensive quality report
    """
    try:
        # Gather results from all quality checks
        grammar_result = step_results.get('check_grammar', {})
        readability_result = step_results.get('analyze_readability', {})
        fact_check_result = step_results.get('fact_check', {})
        plagiarism_result = step_results.get('check_plagiarism', {})
        
        # Calculate overall quality score
        scores = []
        
        if grammar_result:
            scores.append(grammar_result.get('grammar_check', {}).get('score', 0))
        
        if readability_result:
            scores.append(100 if readability_result.get('readability', {}).get('target_appropriate', False) else 70)
        
        if fact_check_result:
            scores.append(fact_check_result.get('fact_check', {}).get('confidence_score', 0))
        
        if plagiarism_result:
            scores.append(plagiarism_result.get('plagiarism_check', {}).get('originality_score', 0))
        
        overall_score = sum(scores) / len(scores) if scores else 0
        
        # Generate report
        report = {
            'overall_quality_score': overall_score,
            'quality_grade': 'A' if overall_score >= 90 else 'B' if overall_score >= 80 else 'C' if overall_score >= 70 else 'D' if overall_score >= 60 else 'F',
            'checks_performed': {
                'grammar': bool(grammar_result),
                'readability': bool(readability_result),
                'fact_checking': bool(fact_check_result),
                'plagiarism': bool(plagiarism_result)
            },
            'summary': {
                'grammar_score': grammar_result.get('grammar_check', {}).get('score', 'N/A'),
                'readability_appropriate': readability_result.get('readability', {}).get('target_appropriate', 'N/A'),
                'factual_confidence': fact_check_result.get('fact_check', {}).get('confidence_score', 'N/A'),
                'originality_score': plagiarism_result.get('plagiarism_check', {}).get('originality_score', 'N/A')
            },
            'recommendations': []
        }
        
        # Add recommendations
        if overall_score < 80:
            report['recommendations'].append('Overall quality needs improvement')
        
        if grammar_result.get('grammar_check', {}).get('issues_count', 0) > 0:
            report['recommendations'].append('Fix grammar and spelling errors')
        
        if not readability_result.get('readability', {}).get('target_appropriate', True):
            report['recommendations'].append('Adjust readability for target audience')
        
        if fact_check_result.get('fact_check', {}).get('facts_found', 0) > 0:
            report['recommendations'].append('Verify factual claims')
        
        if plagiarism_result.get('plagiarism_check', {}).get('originality_score', 100) < 80:
            report['recommendations'].append('Improve content originality')
        
        return {
            'status': 'completed',
            'quality_report': report,
            'context': {
                'quality_report_generated': True,
                'overall_quality_score': overall_score,
                'quality_grade': report['quality_grade']
            },
            'output': {
                'report': report,
                'score': overall_score,
                'grade': report['quality_grade']
            }
        }
        
    except Exception as e:
        logger.error(f"Quality report generation failed: {e}")
        raise