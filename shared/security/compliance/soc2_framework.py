"""SOC2 Compliance Framework

Implements SOC2 Type II compliance controls and monitoring for the five trust principles:
Security, Availability, Processing Integrity, Confidentiality, and Privacy.
"""

import json
from typing import Dict, List, Optional, Any, Set, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
from abc import ABC, abstractmethod
import redis
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib

logger = logging.getLogger(__name__)


class TrustPrinciple(Enum):
    """SOC2 Trust Service Principles"""
    SECURITY = "security"
    AVAILABILITY = "availability"
    PROCESSING_INTEGRITY = "processing_integrity"
    CONFIDENTIALITY = "confidentiality"
    PRIVACY = "privacy"


class ControlCategory(Enum):
    """Control categories"""
    PREVENTIVE = "preventive"
    DETECTIVE = "detective"
    CORRECTIVE = "corrective"
    COMPENSATING = "compensating"


class ComplianceStatus(Enum):
    """Compliance status levels"""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"
    PENDING_REVIEW = "pending_review"


@dataclass
class Control:
    """SOC2 control definition"""
    control_id: str
    name: str
    description: str
    trust_principles: List[TrustPrinciple]
    category: ControlCategory
    requirements: List[str]
    test_procedures: List[str]
    frequency: str  # "continuous", "daily", "weekly", "monthly", "quarterly", "annual"
    responsible_party: str
    automated: bool = True
    enabled: bool = True
    last_tested: Optional[datetime] = None
    last_result: Optional[ComplianceStatus] = None


@dataclass
class ComplianceCheck:
    """Compliance check result"""
    check_id: str
    control_id: str
    timestamp: datetime
    status: ComplianceStatus
    details: Dict[str, Any]
    evidence: List[str] = field(default_factory=list)
    exceptions: List[str] = field(default_factory=list)
    remediation_required: bool = False
    remediation_plan: Optional[str] = None


@dataclass
class Incident:
    """Security incident for compliance tracking"""
    incident_id: str
    timestamp: datetime
    type: str
    severity: str  # "low", "medium", "high", "critical"
    description: str
    affected_systems: List[str]
    response_actions: List[str]
    resolved: bool = False
    resolution_time: Optional[timedelta] = None
    root_cause: Optional[str] = None


class ComplianceMonitor(ABC):
    """Abstract base class for compliance monitors"""
    
    @abstractmethod
    async def check_compliance(self) -> ComplianceCheck:
        """Check compliance for this monitor"""
        pass
    
    @abstractmethod
    def get_control_id(self) -> str:
        """Get the control ID this monitor checks"""
        pass


class SOC2Framework:
    """SOC2 Compliance Framework implementation"""
    
    # Core SOC2 controls
    CONTROLS = {
        # Security Principle
        "CC6.1": Control(
            control_id="CC6.1",
            name="Logical Access Controls",
            description="The entity implements logical access security software, infrastructure, and architectures",
            trust_principles=[TrustPrinciple.SECURITY],
            category=ControlCategory.PREVENTIVE,
            requirements=[
                "Multi-factor authentication for privileged accounts",
                "Role-based access control (RBAC)",
                "Regular access reviews",
                "Password complexity requirements",
                "Account lockout policies"
            ],
            test_procedures=[
                "Review authentication configurations",
                "Test MFA enforcement",
                "Verify RBAC implementation",
                "Check password policies"
            ],
            frequency="continuous",
            responsible_party="Security Team"
        ),
        
        "CC6.2": Control(
            control_id="CC6.2",
            name="System Boundaries",
            description="Prior to issuing system credentials, the entity registers and authorizes new users",
            trust_principles=[TrustPrinciple.SECURITY],
            category=ControlCategory.PREVENTIVE,
            requirements=[
                "User registration process",
                "Identity verification",
                "Access approval workflow",
                "Provisioning procedures"
            ],
            test_procedures=[
                "Review user onboarding process",
                "Test access request workflow",
                "Verify identity verification procedures"
            ],
            frequency="monthly",
            responsible_party="Security Team"
        ),
        
        "CC6.3": Control(
            control_id="CC6.3",
            name="Access Removal",
            description="The entity removes access to systems and data on a timely basis",
            trust_principles=[TrustPrinciple.SECURITY],
            category=ControlCategory.PREVENTIVE,
            requirements=[
                "Termination procedures",
                "Access revocation process",
                "Regular access reviews",
                "Automated deprovisioning"
            ],
            test_procedures=[
                "Review termination procedures",
                "Test access revocation",
                "Verify timely removal"
            ],
            frequency="monthly",
            responsible_party="HR and Security Team"
        ),
        
        "CC7.1": Control(
            control_id="CC7.1",
            name="Vulnerability Management",
            description="The entity identifies, evaluates, and manages vulnerabilities",
            trust_principles=[TrustPrinciple.SECURITY],
            category=ControlCategory.DETECTIVE,
            requirements=[
                "Vulnerability scanning",
                "Patch management",
                "Security assessments",
                "Remediation tracking"
            ],
            test_procedures=[
                "Review vulnerability scan results",
                "Check patch status",
                "Verify remediation timelines"
            ],
            frequency="weekly",
            responsible_party="Security Team"
        ),
        
        "CC7.2": Control(
            control_id="CC7.2",
            name="System Monitoring",
            description="The entity monitors system components for anomalies",
            trust_principles=[TrustPrinciple.SECURITY, TrustPrinciple.AVAILABILITY],
            category=ControlCategory.DETECTIVE,
            requirements=[
                "Log collection and analysis",
                "Intrusion detection",
                "Performance monitoring",
                "Alert mechanisms"
            ],
            test_procedures=[
                "Review monitoring configurations",
                "Test alert mechanisms",
                "Verify log retention"
            ],
            frequency="continuous",
            responsible_party="Operations Team"
        ),
        
        # Availability Principle
        "A1.1": Control(
            control_id="A1.1",
            name="Capacity Planning",
            description="The entity maintains, monitors, and evaluates current processing capacity",
            trust_principles=[TrustPrinciple.AVAILABILITY],
            category=ControlCategory.PREVENTIVE,
            requirements=[
                "Capacity monitoring",
                "Performance metrics",
                "Scaling procedures",
                "Resource planning"
            ],
            test_procedures=[
                "Review capacity metrics",
                "Test scaling procedures",
                "Verify resource allocation"
            ],
            frequency="weekly",
            responsible_party="Operations Team"
        ),
        
        "A1.2": Control(
            control_id="A1.2",
            name="Backup and Recovery",
            description="The entity implements backup and recovery procedures",
            trust_principles=[TrustPrinciple.AVAILABILITY],
            category=ControlCategory.CORRECTIVE,
            requirements=[
                "Regular backups",
                "Backup testing",
                "Recovery procedures",
                "RTO/RPO compliance"
            ],
            test_procedures=[
                "Verify backup completion",
                "Test recovery procedures",
                "Measure RTO/RPO"
            ],
            frequency="monthly",
            responsible_party="Operations Team"
        ),
        
        # Processing Integrity
        "PI1.1": Control(
            control_id="PI1.1",
            name="Data Validation",
            description="The entity validates input data for completeness and accuracy",
            trust_principles=[TrustPrinciple.PROCESSING_INTEGRITY],
            category=ControlCategory.PREVENTIVE,
            requirements=[
                "Input validation rules",
                "Data quality checks",
                "Error handling procedures",
                "Data reconciliation"
            ],
            test_procedures=[
                "Test validation rules",
                "Review error logs",
                "Verify data accuracy"
            ],
            frequency="continuous",
            responsible_party="Development Team"
        ),
        
        # Confidentiality
        "C1.1": Control(
            control_id="C1.1",
            name="Data Classification",
            description="The entity classifies data based on sensitivity",
            trust_principles=[TrustPrinciple.CONFIDENTIALITY],
            category=ControlCategory.PREVENTIVE,
            requirements=[
                "Data classification policy",
                "Labeling procedures",
                "Access restrictions",
                "Encryption requirements"
            ],
            test_procedures=[
                "Review classification policy",
                "Verify data labeling",
                "Test access controls"
            ],
            frequency="quarterly",
            responsible_party="Data Governance Team"
        ),
        
        "C1.2": Control(
            control_id="C1.2",
            name="Encryption",
            description="The entity encrypts confidential information",
            trust_principles=[TrustPrinciple.CONFIDENTIALITY],
            category=ControlCategory.PREVENTIVE,
            requirements=[
                "Encryption at rest",
                "Encryption in transit",
                "Key management",
                "Crypto standards"
            ],
            test_procedures=[
                "Verify encryption implementation",
                "Test key rotation",
                "Review crypto standards"
            ],
            frequency="monthly",
            responsible_party="Security Team"
        ),
        
        # Privacy
        "P1.1": Control(
            control_id="P1.1",
            name="Privacy Notice",
            description="The entity provides notice about privacy practices",
            trust_principles=[TrustPrinciple.PRIVACY],
            category=ControlCategory.PREVENTIVE,
            requirements=[
                "Privacy policy",
                "Consent mechanisms",
                "Data usage disclosure",
                "Third-party sharing"
            ],
            test_procedures=[
                "Review privacy policy",
                "Test consent mechanisms",
                "Verify disclosure accuracy"
            ],
            frequency="quarterly",
            responsible_party="Legal Team"
        ),
        
        "P3.1": Control(
            control_id="P3.1",
            name="Data Subject Rights",
            description="The entity provides data subjects with access to their personal information",
            trust_principles=[TrustPrinciple.PRIVACY],
            category=ControlCategory.PREVENTIVE,
            requirements=[
                "Access request procedures",
                "Data portability",
                "Deletion procedures",
                "Correction mechanisms"
            ],
            test_procedures=[
                "Test access request process",
                "Verify data export",
                "Test deletion procedures"
            ],
            frequency="monthly",
            responsible_party="Privacy Team"
        )
    }
    
    def __init__(
        self,
        redis_client: redis.Redis,
        audit_logger,  # AuditLogger instance
        enable_automated_checks: bool = True,
        check_interval: int = 3600,  # 1 hour
        alert_handler: Optional[Callable] = None
    ):
        self.redis_client = redis_client
        self.audit_logger = audit_logger
        self.enable_automated_checks = enable_automated_checks
        self.check_interval = check_interval
        self.alert_handler = alert_handler
        
        # Compliance monitors
        self.monitors: Dict[str, ComplianceMonitor] = {}
        
        # Incident tracking
        self.incidents: List[Incident] = []
        
        # Initialize default monitors
        self._initialize_monitors()
        
        # Start automated checking if enabled
        if enable_automated_checks:
            self._start_automated_checks()
    
    def _initialize_monitors(self):
        """Initialize built-in compliance monitors"""
        # Add monitors for each control
        # This is where you'd implement specific monitors
        pass
    
    def add_monitor(self, monitor: ComplianceMonitor):
        """Add a compliance monitor"""
        control_id = monitor.get_control_id()
        self.monitors[control_id] = monitor
        logger.info(f"Added monitor for control: {control_id}")
    
    async def check_control(self, control_id: str) -> ComplianceCheck:
        """Check compliance for a specific control"""
        if control_id not in self.CONTROLS:
            raise ValueError(f"Unknown control: {control_id}")
        
        control = self.CONTROLS[control_id]
        
        # Use automated monitor if available
        if control_id in self.monitors and control.automated:
            try:
                return await self.monitors[control_id].check_compliance()
            except Exception as e:
                logger.error(f"Monitor failed for {control_id}: {str(e)}")
                return ComplianceCheck(
                    check_id=f"check_{control_id}_{datetime.utcnow().isoformat()}",
                    control_id=control_id,
                    timestamp=datetime.utcnow(),
                    status=ComplianceStatus.PENDING_REVIEW,
                    details={"error": str(e)},
                    remediation_required=True
                )
        
        # Manual check placeholder
        return ComplianceCheck(
            check_id=f"check_{control_id}_{datetime.utcnow().isoformat()}",
            control_id=control_id,
            timestamp=datetime.utcnow(),
            status=ComplianceStatus.PENDING_REVIEW,
            details={"message": "Manual review required"}
        )
    
    async def run_compliance_assessment(
        self,
        trust_principles: Optional[List[TrustPrinciple]] = None
    ) -> Dict[str, ComplianceCheck]:
        """Run comprehensive compliance assessment"""
        results = {}
        
        # Filter controls by trust principles if specified
        controls_to_check = self.CONTROLS.values()
        if trust_principles:
            controls_to_check = [
                c for c in controls_to_check
                if any(tp in c.trust_principles for tp in trust_principles)
            ]
        
        # Check each control
        for control in controls_to_check:
            if control.enabled:
                check = await self.check_control(control.control_id)
                results[control.control_id] = check
                
                # Store result
                self._store_compliance_check(check)
                
                # Log to audit
                self.audit_logger.log_event(
                    event_type="compliance.check",
                    metadata={
                        "control_id": control.control_id,
                        "status": check.status.value,
                        "details": check.details
                    }
                )
                
                # Alert if non-compliant
                if check.status == ComplianceStatus.NON_COMPLIANT:
                    await self._handle_non_compliance(control, check)
        
        return results
    
    def generate_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime,
        trust_principles: Optional[List[TrustPrinciple]] = None
    ) -> Dict[str, Any]:
        """Generate SOC2 compliance report"""
        report = {
            "report_id": f"soc2_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "trust_principles": [tp.value for tp in trust_principles] if trust_principles else "all",
            "summary": {},
            "controls": {},
            "incidents": [],
            "exceptions": [],
            "attestation": {}
        }
        
        # Get compliance checks for period
        checks = self._get_compliance_checks(start_date, end_date)
        
        # Analyze by control
        for control_id, control in self.CONTROLS.items():
            if trust_principles and not any(tp in control.trust_principles for tp in trust_principles):
                continue
            
            control_checks = [c for c in checks if c.control_id == control_id]
            
            if control_checks:
                # Calculate compliance rate
                compliant_count = sum(1 for c in control_checks if c.status == ComplianceStatus.COMPLIANT)
                total_count = len(control_checks)
                compliance_rate = (compliant_count / total_count) * 100 if total_count > 0 else 0
                
                report["controls"][control_id] = {
                    "name": control.name,
                    "trust_principles": [tp.value for tp in control.trust_principles],
                    "total_checks": total_count,
                    "compliant_checks": compliant_count,
                    "compliance_rate": compliance_rate,
                    "last_check": control_checks[-1].timestamp.isoformat(),
                    "status": self._determine_control_status(compliance_rate)
                }
        
        # Add incidents
        period_incidents = [
            i for i in self.incidents
            if start_date <= i.timestamp <= end_date
        ]
        report["incidents"] = [
            {
                "incident_id": i.incident_id,
                "timestamp": i.timestamp.isoformat(),
                "type": i.type,
                "severity": i.severity,
                "resolved": i.resolved,
                "resolution_time": str(i.resolution_time) if i.resolution_time else None
            }
            for i in period_incidents
        ]
        
        # Generate summary
        total_controls = len(report["controls"])
        compliant_controls = sum(1 for c in report["controls"].values() if c["status"] == "compliant")
        
        report["summary"] = {
            "total_controls": total_controls,
            "compliant_controls": compliant_controls,
            "compliance_percentage": (compliant_controls / total_controls * 100) if total_controls > 0 else 0,
            "total_incidents": len(period_incidents),
            "critical_incidents": sum(1 for i in period_incidents if i.severity == "critical"),
            "average_resolution_time": self._calculate_average_resolution_time(period_incidents)
        }
        
        # Add attestation
        report["attestation"] = {
            "statement": "Based on our assessment, the system's controls were operating effectively during the period.",
            "qualified": report["summary"]["compliance_percentage"] < 100,
            "qualifications": self._generate_qualifications(report)
        }
        
        # Store report
        self._store_report(report)
        
        # Log report generation
        self.audit_logger.log_event(
            event_type="compliance.report.generated",
            metadata={
                "report_id": report["report_id"],
                "period": f"{start_date} to {end_date}",
                "compliance_percentage": report["summary"]["compliance_percentage"]
            }
        )
        
        return report
    
    def record_incident(
        self,
        incident_type: str,
        severity: str,
        description: str,
        affected_systems: List[str],
        response_actions: List[str]
    ) -> str:
        """Record a security incident"""
        incident = Incident(
            incident_id=f"INC_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{hashlib.sha256(description.encode()).hexdigest()[:8]}",
            timestamp=datetime.utcnow(),
            type=incident_type,
            severity=severity,
            description=description,
            affected_systems=affected_systems,
            response_actions=response_actions
        )
        
        self.incidents.append(incident)
        self._store_incident(incident)
        
        # Log to audit
        self.audit_logger.log_security_event(
            threat_type=incident_type,
            severity=severity,
            description=description,
            metadata={
                "incident_id": incident.incident_id,
                "affected_systems": affected_systems
            }
        )
        
        return incident.incident_id
    
    def resolve_incident(
        self,
        incident_id: str,
        root_cause: str,
        additional_actions: Optional[List[str]] = None
    ):
        """Mark incident as resolved"""
        incident = next((i for i in self.incidents if i.incident_id == incident_id), None)
        
        if not incident:
            raise ValueError(f"Incident not found: {incident_id}")
        
        incident.resolved = True
        incident.resolution_time = datetime.utcnow() - incident.timestamp
        incident.root_cause = root_cause
        
        if additional_actions:
            incident.response_actions.extend(additional_actions)
        
        self._store_incident(incident)
        
        # Log resolution
        self.audit_logger.log_event(
            event_type="compliance.incident.resolved",
            metadata={
                "incident_id": incident_id,
                "resolution_time": str(incident.resolution_time),
                "root_cause": root_cause
            }
        )
    
    def _store_compliance_check(self, check: ComplianceCheck):
        """Store compliance check result"""
        key = f"compliance:check:{check.control_id}:{check.check_id}"
        self.redis_client.setex(
            key,
            86400 * 365,  # 1 year retention
            json.dumps(check.__dict__, default=str)
        )
        
        # Add to index
        score = check.timestamp.timestamp()
        self.redis_client.zadd(
            f"compliance:checks:{check.control_id}",
            {check.check_id: score}
        )
    
    def _get_compliance_checks(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[ComplianceCheck]:
        """Get compliance checks for date range"""
        checks = []
        
        for control_id in self.CONTROLS:
            # Get checks from sorted set
            check_ids = self.redis_client.zrangebyscore(
                f"compliance:checks:{control_id}",
                start_date.timestamp(),
                end_date.timestamp()
            )
            
            for check_id in check_ids:
                key = f"compliance:check:{control_id}:{check_id.decode() if isinstance(check_id, bytes) else check_id}"
                data = self.redis_client.get(key)
                if data:
                    check_dict = json.loads(data)
                    # Convert back to ComplianceCheck
                    checks.append(ComplianceCheck(**check_dict))
        
        return checks
    
    def _determine_control_status(self, compliance_rate: float) -> str:
        """Determine control status based on compliance rate"""
        if compliance_rate >= 95:
            return "compliant"
        elif compliance_rate >= 80:
            return "partial"
        else:
            return "non_compliant"
    
    def _calculate_average_resolution_time(self, incidents: List[Incident]) -> str:
        """Calculate average incident resolution time"""
        resolved_incidents = [i for i in incidents if i.resolved and i.resolution_time]
        
        if not resolved_incidents:
            return "N/A"
        
        total_time = sum(i.resolution_time.total_seconds() for i in resolved_incidents)
        average_seconds = total_time / len(resolved_incidents)
        
        return str(timedelta(seconds=int(average_seconds)))
    
    def _generate_qualifications(self, report: Dict[str, Any]) -> List[str]:
        """Generate report qualifications"""
        qualifications = []
        
        # Check for non-compliant controls
        for control_id, control_data in report["controls"].items():
            if control_data["status"] == "non_compliant":
                qualifications.append(
                    f"Control {control_id} ({control_data['name']}) did not meet compliance requirements"
                )
        
        # Check for critical incidents
        critical_incidents = [i for i in report["incidents"] if i["severity"] == "critical"]
        if critical_incidents:
            qualifications.append(
                f"{len(critical_incidents)} critical security incidents occurred during the period"
            )
        
        return qualifications
    
    def _store_report(self, report: Dict[str, Any]):
        """Store compliance report"""
        key = f"compliance:report:{report['report_id']}"
        self.redis_client.set(key, json.dumps(report))
        
        # Add to index
        self.redis_client.zadd(
            "compliance:reports",
            {report['report_id']: datetime.utcnow().timestamp()}
        )
    
    def _store_incident(self, incident: Incident):
        """Store incident"""
        key = f"compliance:incident:{incident.incident_id}"
        self.redis_client.set(
            key,
            json.dumps(incident.__dict__, default=str)
        )
    
    async def _handle_non_compliance(self, control: Control, check: ComplianceCheck):
        """Handle non-compliance detection"""
        # Send alert
        if self.alert_handler:
            await self.alert_handler({
                "type": "compliance_violation",
                "control_id": control.control_id,
                "control_name": control.name,
                "status": check.status.value,
                "details": check.details,
                "timestamp": check.timestamp.isoformat()
            })
        
        # Create incident if critical
        if control.trust_principles == [TrustPrinciple.SECURITY]:
            self.record_incident(
                incident_type="compliance_violation",
                severity="high",
                description=f"Non-compliance detected for control {control.control_id}: {control.name}",
                affected_systems=[control.control_id],
                response_actions=["Automated alert sent", "Manual review required"]
            )
    
    def _start_automated_checks(self):
        """Start automated compliance checking"""
        async def check_loop():
            while True:
                try:
                    # Run checks for controls due
                    for control in self.CONTROLS.values():
                        if self._is_check_due(control):
                            await self.check_control(control.control_id)
                    
                    await asyncio.sleep(self.check_interval)
                except Exception as e:
                    logger.error(f"Error in automated compliance checks: {str(e)}")
                    await asyncio.sleep(60)  # Wait before retrying
        
        # Start in background
        asyncio.create_task(check_loop())
    
    def _is_check_due(self, control: Control) -> bool:
        """Check if control is due for checking"""
        if not control.last_tested:
            return True
        
        # Map frequency to timedelta
        frequency_map = {
            "continuous": timedelta(hours=1),
            "daily": timedelta(days=1),
            "weekly": timedelta(days=7),
            "monthly": timedelta(days=30),
            "quarterly": timedelta(days=90),
            "annual": timedelta(days=365)
        }
        
        interval = frequency_map.get(control.frequency, timedelta(days=1))
        return datetime.utcnow() - control.last_tested >= interval