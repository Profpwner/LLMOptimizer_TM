"""
CI/CD Security Integration Module for LLMOptimizer

This module provides integration between the security testing framework
and various CI/CD platforms (GitHub Actions, Jenkins, GitLab).
"""

import os
import json
import yaml
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
import jwt
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend

from .security_test_framework import SecurityTestFramework, SecurityTestResult
from ..shared.compliance.compliance_manager import ComplianceManager
from ..shared.compliance.audit_reports import AuditReportGenerator

logger = logging.getLogger(__name__)

class CICDPlatform(Enum):
    """Supported CI/CD platforms"""
    GITHUB_ACTIONS = "github_actions"
    JENKINS = "jenkins"
    GITLAB = "gitlab"
    AZURE_DEVOPS = "azure_devops"
    CIRCLECI = "circleci"
    BITBUCKET_PIPELINES = "bitbucket_pipelines"

class GateStatus(Enum):
    """Security gate status"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    OVERRIDE = "override"

@dataclass
class SecurityGateResult:
    """Result from a security gate check"""
    gate_name: str
    status: GateStatus
    findings: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_seconds: float = 0.0
    override_reason: Optional[str] = None
    override_approver: Optional[str] = None

@dataclass
class CICDSecurityReport:
    """Comprehensive CI/CD security report"""
    build_id: str
    platform: CICDPlatform
    branch: str
    commit_sha: str
    gate_results: List[SecurityGateResult]
    overall_status: GateStatus
    security_score: float
    compliance_status: Dict[str, bool]
    recommendations: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)

class GitHubActionsIntegration:
    """GitHub Actions security integration"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_token = os.environ.get('GITHUB_TOKEN')
        self.repo_owner = config.get('repo_owner')
        self.repo_name = config.get('repo_name')
        self.api_base = "https://api.github.com"
        
    async def create_status_check(
        self,
        commit_sha: str,
        context: str,
        state: str,
        description: str,
        target_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a GitHub status check"""
        url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/statuses/{commit_sha}"
        
        payload = {
            "state": state,
            "description": description[:140],  # GitHub limit
            "context": f"security/{context}",
        }
        
        if target_url:
            payload["target_url"] = target_url
            
        headers = {
            "Authorization": f"token {self.api_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                return await response.json()
    
    async def create_check_run(
        self,
        head_sha: str,
        name: str,
        status: str,
        conclusion: Optional[str] = None,
        output: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a GitHub check run with detailed output"""
        url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/check-runs"
        
        payload = {
            "name": f"Security Gate: {name}",
            "head_sha": head_sha,
            "status": status,
        }
        
        if conclusion:
            payload["conclusion"] = conclusion
            payload["completed_at"] = datetime.utcnow().isoformat() + "Z"
            
        if output:
            payload["output"] = output
            
        headers = {
            "Authorization": f"token {self.api_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                return await response.json()
    
    async def create_issue_for_findings(
        self,
        title: str,
        findings: List[Dict[str, Any]],
        labels: List[str] = None
    ) -> Dict[str, Any]:
        """Create GitHub issue for security findings"""
        url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/issues"
        
        # Format findings into issue body
        body = f"## Security Findings\n\n"
        body += f"**Build:** {os.environ.get('GITHUB_RUN_ID', 'N/A')}\n"
        body += f"**Commit:** {os.environ.get('GITHUB_SHA', 'N/A')}\n\n"
        
        for finding in findings:
            body += f"### {finding.get('title', 'Finding')}\n"
            body += f"- **Severity:** {finding.get('severity', 'Unknown')}\n"
            body += f"- **Category:** {finding.get('category', 'General')}\n"
            body += f"- **Description:** {finding.get('description', '')}\n"
            if 'file' in finding:
                body += f"- **File:** `{finding['file']}`\n"
            if 'line' in finding:
                body += f"- **Line:** {finding['line']}\n"
            body += "\n"
            
        payload = {
            "title": title,
            "body": body,
            "labels": labels or ["security", "automated"]
        }
        
        headers = {
            "Authorization": f"token {self.api_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                return await response.json()
    
    async def update_branch_protection(
        self,
        branch: str,
        required_checks: List[str]
    ) -> Dict[str, Any]:
        """Update branch protection rules with security requirements"""
        url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/branches/{branch}/protection"
        
        payload = {
            "required_status_checks": {
                "strict": True,
                "contexts": [f"security/{check}" for check in required_checks]
            },
            "enforce_admins": True,
            "required_pull_request_reviews": {
                "required_approving_review_count": 2,
                "dismiss_stale_reviews": True,
                "require_code_owner_reviews": True,
                "dismissal_restrictions": {
                    "teams": ["security-team"]
                }
            },
            "restrictions": None,
            "allow_force_pushes": False,
            "allow_deletions": False
        }
        
        headers = {
            "Authorization": f"token {self.api_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.put(url, json=payload, headers=headers) as response:
                return await response.json()

class JenkinsIntegration:
    """Jenkins security integration"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.jenkins_url = config.get('jenkins_url')
        self.api_user = config.get('api_user')
        self.api_token = os.environ.get('JENKINS_API_TOKEN')
        
    async def trigger_security_pipeline(
        self,
        job_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Trigger Jenkins security pipeline"""
        url = f"{self.jenkins_url}/job/{job_name}/buildWithParameters"
        
        auth = aiohttp.BasicAuth(self.api_user, self.api_token)
        
        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.post(url, data=parameters) as response:
                location = response.headers.get('Location')
                return {
                    "status": "triggered",
                    "queue_url": location
                }
    
    async def get_build_status(self, job_name: str, build_number: int) -> Dict[str, Any]:
        """Get Jenkins build status"""
        url = f"{self.jenkins_url}/job/{job_name}/{build_number}/api/json"
        
        auth = aiohttp.BasicAuth(self.api_user, self.api_token)
        
        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.get(url) as response:
                return await response.json()
    
    async def publish_test_results(
        self,
        job_name: str,
        build_number: int,
        results: Dict[str, Any]
    ) -> bool:
        """Publish test results to Jenkins"""
        # Jenkins typically reads from workspace files
        # This would integrate with Jenkins plugins
        return True

class GitLabIntegration:
    """GitLab security integration"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.gitlab_url = config.get('gitlab_url', 'https://gitlab.com')
        self.project_id = config.get('project_id')
        self.api_token = os.environ.get('GITLAB_TOKEN')
        
    async def create_pipeline_status(
        self,
        commit_sha: str,
        state: str,
        name: str,
        description: str
    ) -> Dict[str, Any]:
        """Create GitLab pipeline status"""
        url = f"{self.gitlab_url}/api/v4/projects/{self.project_id}/statuses/{commit_sha}"
        
        payload = {
            "state": state,
            "name": f"security/{name}",
            "description": description
        }
        
        headers = {
            "PRIVATE-TOKEN": self.api_token
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                return await response.json()
    
    async def create_merge_request_note(
        self,
        mr_iid: int,
        body: str
    ) -> Dict[str, Any]:
        """Add security findings as MR comment"""
        url = f"{self.gitlab_url}/api/v4/projects/{self.project_id}/merge_requests/{mr_iid}/notes"
        
        payload = {"body": body}
        headers = {"PRIVATE-TOKEN": self.api_token}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                return await response.json()

class CICDSecurityIntegration:
    """Main CI/CD security integration orchestrator"""
    
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        self.security_framework = SecurityTestFramework()
        self.compliance_manager = ComplianceManager()
        self.report_generator = AuditReportGenerator()
        
        # Initialize platform integrations
        self.integrations = {
            CICDPlatform.GITHUB_ACTIONS: GitHubActionsIntegration(
                self.config.get('integrations', {}).get('github_actions', {})
            ),
            CICDPlatform.JENKINS: JenkinsIntegration(
                self.config.get('integrations', {}).get('jenkins', {})
            ),
            CICDPlatform.GITLAB: GitLabIntegration(
                self.config.get('integrations', {}).get('gitlab', {})
            )
        }
        
    async def run_security_gates(
        self,
        stage: str,
        platform: CICDPlatform,
        build_context: Dict[str, Any]
    ) -> CICDSecurityReport:
        """Run security gates for a specific stage"""
        logger.info(f"Running security gates for stage: {stage}")
        
        gate_configs = self.config['security_gates'].get(stage, [])
        gate_results = []
        overall_status = GateStatus.PASSED
        
        for gate_config in gate_configs:
            result = await self._run_single_gate(gate_config, build_context)
            gate_results.append(result)
            
            if result.status == GateStatus.FAILED:
                overall_status = GateStatus.FAILED
            elif result.status == GateStatus.WARNING and overall_status == GateStatus.PASSED:
                overall_status = GateStatus.WARNING
                
        # Calculate security score
        security_score = self._calculate_security_score(gate_results)
        
        # Check compliance
        compliance_status = await self._check_compliance_requirements(stage, gate_results)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(gate_results, compliance_status)
        
        report = CICDSecurityReport(
            build_id=build_context.get('build_id', 'unknown'),
            platform=platform,
            branch=build_context.get('branch', 'unknown'),
            commit_sha=build_context.get('commit_sha', 'unknown'),
            gate_results=gate_results,
            overall_status=overall_status,
            security_score=security_score,
            compliance_status=compliance_status,
            recommendations=recommendations
        )
        
        # Update CI/CD platform
        await self._update_platform_status(platform, report, build_context)
        
        # Handle gate failures
        if overall_status == GateStatus.FAILED:
            await self._handle_gate_failure(stage, platform, report, build_context)
            
        return report
    
    async def _run_single_gate(
        self,
        gate_config: Dict[str, Any],
        build_context: Dict[str, Any]
    ) -> SecurityGateResult:
        """Run a single security gate"""
        gate_name = gate_config['name']
        start_time = datetime.utcnow()
        
        try:
            # Run the appropriate tool/check
            if 'tool' in gate_config:
                findings = await self._run_security_tool(
                    gate_config['tool'],
                    gate_config.get('config', {}),
                    build_context
                )
            elif 'tools' in gate_config:
                findings = []
                for tool_config in gate_config['tools']:
                    tool_findings = await self._run_security_tool(
                        tool_config['name'],
                        tool_config,
                        build_context
                    )
                    findings.extend(tool_findings)
            else:
                findings = []
                
            # Evaluate against failure criteria
            status = self._evaluate_gate_criteria(
                findings,
                gate_config.get('fail_on', {}),
                gate_config.get('quality_gates', {})
            )
            
            # Calculate metrics
            metrics = self._calculate_gate_metrics(findings)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            return SecurityGateResult(
                gate_name=gate_name,
                status=status,
                findings=findings,
                metrics=metrics,
                duration_seconds=duration
            )
            
        except Exception as e:
            logger.error(f"Error running gate {gate_name}: {str(e)}")
            return SecurityGateResult(
                gate_name=gate_name,
                status=GateStatus.FAILED,
                findings=[{
                    "type": "error",
                    "message": str(e)
                }],
                duration_seconds=(datetime.utcnow() - start_time).total_seconds()
            )
    
    async def _run_security_tool(
        self,
        tool_name: str,
        tool_config: Dict[str, Any],
        build_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Run a specific security tool"""
        # This would integrate with actual security tools
        # For now, return mock findings
        if tool_name == "bandit":
            return await self._run_bandit(tool_config)
        elif tool_name == "safety":
            return await self._run_safety(tool_config)
        elif tool_name == "trivy":
            return await self._run_trivy(tool_config)
        # Add more tools as needed
        return []
    
    async def _run_bandit(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run Bandit static analysis"""
        # Integration with actual Bandit tool
        return []
    
    async def _run_safety(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run Safety dependency check"""
        # Integration with actual Safety tool
        return []
    
    async def _run_trivy(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run Trivy container scanning"""
        # Integration with actual Trivy tool
        return []
    
    def _evaluate_gate_criteria(
        self,
        findings: List[Dict[str, Any]],
        fail_criteria: Dict[str, Any],
        quality_gates: Dict[str, Any]
    ) -> GateStatus:
        """Evaluate if gate passes based on criteria"""
        # Check severity-based criteria
        if 'severity' in fail_criteria:
            for finding in findings:
                if finding.get('severity') in fail_criteria['severity']:
                    return GateStatus.FAILED
                    
        # Check CVSS score criteria
        if 'cvss_score' in fail_criteria:
            for finding in findings:
                if finding.get('cvss_score', 0) >= fail_criteria['cvss_score']:
                    return GateStatus.FAILED
                    
        # Check quality gates
        for metric, threshold in quality_gates.items():
            current_value = self._get_metric_value(findings, metric)
            if not self._meets_threshold(current_value, threshold, metric):
                return GateStatus.FAILED
                
        # Check if any findings at all should fail
        if fail_criteria.get('findings') and findings:
            return GateStatus.FAILED
            
        # Warnings for medium severity
        for finding in findings:
            if finding.get('severity') == 'medium':
                return GateStatus.WARNING
                
        return GateStatus.PASSED
    
    def _calculate_gate_metrics(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate metrics from findings"""
        metrics = {
            "total_findings": len(findings),
            "critical": sum(1 for f in findings if f.get('severity') == 'critical'),
            "high": sum(1 for f in findings if f.get('severity') == 'high'),
            "medium": sum(1 for f in findings if f.get('severity') == 'medium'),
            "low": sum(1 for f in findings if f.get('severity') == 'low'),
        }
        
        # Calculate average CVSS score
        cvss_scores = [f.get('cvss_score', 0) for f in findings if 'cvss_score' in f]
        if cvss_scores:
            metrics['avg_cvss_score'] = sum(cvss_scores) / len(cvss_scores)
            
        return metrics
    
    def _calculate_security_score(self, gate_results: List[SecurityGateResult]) -> float:
        """Calculate overall security score (0-100)"""
        if not gate_results:
            return 100.0
            
        total_weight = 0
        weighted_score = 0
        
        # Weight by gate importance
        gate_weights = {
            "Secret Scanning": 20,
            "Dependency Vulnerability Check": 20,
            "Static Code Analysis": 15,
            "Container Security": 15,
            "Security Unit Tests": 10,
            "DAST Scanning": 10,
            "License Compliance": 5,
            "Other": 5
        }
        
        for result in gate_results:
            weight = gate_weights.get(result.gate_name, gate_weights["Other"])
            total_weight += weight
            
            if result.status == GateStatus.PASSED:
                weighted_score += weight
            elif result.status == GateStatus.WARNING:
                weighted_score += weight * 0.7
            elif result.status == GateStatus.SKIPPED:
                weighted_score += weight * 0.5
                
        return (weighted_score / total_weight) * 100 if total_weight > 0 else 0
    
    async def _check_compliance_requirements(
        self,
        stage: str,
        gate_results: List[SecurityGateResult]
    ) -> Dict[str, bool]:
        """Check compliance requirements based on gate results"""
        compliance_status = {}
        
        # SOC2 requirements
        compliance_status['soc2_security_testing'] = any(
            r.gate_name in ["Security Unit Tests", "DAST Scanning"] and r.status == GateStatus.PASSED
            for r in gate_results
        )
        
        compliance_status['soc2_vulnerability_management'] = any(
            r.gate_name == "Dependency Vulnerability Check" and r.status == GateStatus.PASSED
            for r in gate_results
        )
        
        # GDPR requirements
        compliance_status['gdpr_security_by_design'] = any(
            r.gate_name == "Static Code Analysis" and r.status == GateStatus.PASSED
            for r in gate_results
        )
        
        # PCI-DSS requirements (if applicable)
        compliance_status['pci_secure_development'] = all(
            r.status in [GateStatus.PASSED, GateStatus.WARNING]
            for r in gate_results
            if r.gate_name in ["Static Code Analysis", "Secret Scanning"]
        )
        
        return compliance_status
    
    def _generate_recommendations(
        self,
        gate_results: List[SecurityGateResult],
        compliance_status: Dict[str, bool]
    ) -> List[str]:
        """Generate security recommendations"""
        recommendations = []
        
        # Check for failed gates
        failed_gates = [r for r in gate_results if r.status == GateStatus.FAILED]
        for gate in failed_gates:
            if gate.metrics.get('critical', 0) > 0:
                recommendations.append(
                    f"CRITICAL: Address {gate.metrics['critical']} critical findings in {gate.gate_name}"
                )
            if gate.metrics.get('high', 0) > 0:
                recommendations.append(
                    f"HIGH: Fix {gate.metrics['high']} high-severity issues in {gate.gate_name}"
                )
                
        # Check compliance gaps
        for requirement, met in compliance_status.items():
            if not met:
                recommendations.append(
                    f"COMPLIANCE: {requirement} requirement not met - review security controls"
                )
                
        # General recommendations based on metrics
        total_findings = sum(r.metrics.get('total_findings', 0) for r in gate_results)
        if total_findings > 50:
            recommendations.append(
                "Consider implementing automated remediation for common security issues"
            )
            
        avg_duration = sum(r.duration_seconds for r in gate_results) / len(gate_results)
        if avg_duration > 300:  # 5 minutes
            recommendations.append(
                "Security gates taking long time - consider parallelizing or optimizing scans"
            )
            
        return recommendations
    
    async def _update_platform_status(
        self,
        platform: CICDPlatform,
        report: CICDSecurityReport,
        build_context: Dict[str, Any]
    ):
        """Update CI/CD platform with security status"""
        integration = self.integrations.get(platform)
        if not integration:
            return
            
        if platform == CICDPlatform.GITHUB_ACTIONS:
            # Update GitHub status checks
            for result in report.gate_results:
                state = "success" if result.status == GateStatus.PASSED else "failure"
                await integration.create_status_check(
                    commit_sha=report.commit_sha,
                    context=result.gate_name.lower().replace(" ", "-"),
                    state=state,
                    description=f"{result.metrics.get('total_findings', 0)} findings"
                )
                
            # Create detailed check run
            output = {
                "title": "Security Gate Summary",
                "summary": f"Security Score: {report.security_score:.1f}/100",
                "text": self._format_report_markdown(report)
            }
            
            conclusion = "success" if report.overall_status == GateStatus.PASSED else "failure"
            await integration.create_check_run(
                head_sha=report.commit_sha,
                name="Security Gates",
                status="completed",
                conclusion=conclusion,
                output=output
            )
            
    def _format_report_markdown(self, report: CICDSecurityReport) -> str:
        """Format security report as markdown"""
        md = f"## Security Gate Results\n\n"
        md += f"**Overall Status:** {report.overall_status.value}\n"
        md += f"**Security Score:** {report.security_score:.1f}/100\n\n"
        
        md += "### Gate Results\n\n"
        md += "| Gate | Status | Findings | Duration |\n"
        md += "|------|--------|----------|----------|\n"
        
        for result in report.gate_results:
            status_emoji = {
                GateStatus.PASSED: "✅",
                GateStatus.FAILED: "❌",
                GateStatus.WARNING: "⚠️",
                GateStatus.SKIPPED: "⏭️"
            }.get(result.status, "❓")
            
            md += f"| {result.gate_name} | {status_emoji} {result.status.value} | "
            md += f"{result.metrics.get('total_findings', 0)} | {result.duration_seconds:.1f}s |\n"
            
        md += "\n### Compliance Status\n\n"
        for requirement, met in report.compliance_status.items():
            status = "✅ Met" if met else "❌ Not Met"
            md += f"- **{requirement}:** {status}\n"
            
        if report.recommendations:
            md += "\n### Recommendations\n\n"
            for rec in report.recommendations:
                md += f"- {rec}\n"
                
        return md
    
    async def _handle_gate_failure(
        self,
        stage: str,
        platform: CICDPlatform,
        report: CICDSecurityReport,
        build_context: Dict[str, Any]
    ):
        """Handle security gate failures"""
        enforcement = self.config['enforcement']['failure_actions'].get(stage, {})
        
        # Send notifications
        await self._send_notifications(
            enforcement.get('notify', []),
            report,
            build_context
        )
        
        # Create issue if configured
        if enforcement.get('create_issue'):
            await self._create_security_issue(platform, report, build_context)
            
        # Check for override possibility
        if enforcement.get('action') == 'require-override':
            await self._check_override_approval(
                enforcement.get('override_approvers', []),
                report,
                build_context
            )
    
    async def _send_notifications(
        self,
        recipients: List[str],
        report: CICDSecurityReport,
        build_context: Dict[str, Any]
    ):
        """Send security notifications"""
        # Implementation would integrate with notification systems
        logger.info(f"Sending notifications to: {recipients}")
        
    async def _create_security_issue(
        self,
        platform: CICDPlatform,
        report: CICDSecurityReport,
        build_context: Dict[str, Any]
    ):
        """Create security issue in issue tracker"""
        integration = self.integrations.get(platform)
        if not integration or platform != CICDPlatform.GITHUB_ACTIONS:
            return
            
        # Collect all high/critical findings
        critical_findings = []
        for result in report.gate_results:
            if result.status == GateStatus.FAILED:
                for finding in result.findings:
                    if finding.get('severity') in ['critical', 'high']:
                        critical_findings.append(finding)
                        
        if critical_findings:
            await integration.create_issue_for_findings(
                title=f"Security Gate Failures - Build {report.build_id}",
                findings=critical_findings,
                labels=["security", "automated", "high-priority"]
            )
    
    async def _check_override_approval(
        self,
        required_approvers: List[str],
        report: CICDSecurityReport,
        build_context: Dict[str, Any]
    ):
        """Check if override approval has been granted"""
        # This would integrate with approval systems
        logger.info(f"Checking override approval from: {required_approvers}")
        
    def _get_metric_value(self, findings: List[Dict[str, Any]], metric: str) -> Any:
        """Get metric value from findings"""
        # Implementation depends on specific metrics
        return 0
        
    def _meets_threshold(self, value: Any, threshold: Any, metric: str) -> bool:
        """Check if value meets threshold requirement"""
        # Implementation depends on metric type
        return True

async def main():
    """Example usage"""
    integration = CICDSecurityIntegration("cicd_security_gates.yaml")
    
    # Example build context
    build_context = {
        "build_id": "123",
        "branch": "main",
        "commit_sha": "abc123def456",
        "pull_request": "42"
    }
    
    # Run security gates for build stage
    report = await integration.run_security_gates(
        stage="build",
        platform=CICDPlatform.GITHUB_ACTIONS,
        build_context=build_context
    )
    
    print(f"Security Score: {report.security_score:.1f}/100")
    print(f"Overall Status: {report.overall_status.value}")
    
if __name__ == "__main__":
    asyncio.run(main())