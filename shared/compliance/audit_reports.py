"""
Audit report generation for compliance tracking.
"""

import os
import json
import csv
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, Image, ListFlowable, ListItem
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import xlsxwriter
import logging

logger = logging.getLogger(__name__)


class AuditReportGenerator:
    """Generate comprehensive audit reports for compliance."""
    
    def __init__(self):
        self.reports_dir = Path('compliance/audit_reports')
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom styles for PDF reports."""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=30
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#34495e'),
            spaceAfter=12
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['BodyText'],
            fontSize=10,
            leading=14
        ))
    
    def generate_soc2_audit_report(self, 
                                  assessment_data: Dict[str, Any],
                                  period_start: datetime,
                                  period_end: datetime) -> str:
        """Generate SOC2 Type II audit report."""
        report_id = f"SOC2_AUDIT_{period_end.strftime('%Y%m%d')}"
        filename = self.reports_dir / f"{report_id}.pdf"
        
        doc = SimpleDocTemplate(
            str(filename),
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        story = []
        
        # Title Page
        story.append(Paragraph(
            "SOC2 Type II Audit Report",
            self.styles['CustomTitle']
        ))
        
        story.append(Paragraph(
            f"LLMOptimizer Platform",
            self.styles['Heading2']
        ))
        
        story.append(Spacer(1, 0.5*inch))
        
        story.append(Paragraph(
            f"Audit Period: {period_start.strftime('%B %d, %Y')} - {period_end.strftime('%B %d, %Y')}",
            self.styles['Normal']
        ))
        
        story.append(Paragraph(
            f"Report Generated: {datetime.now().strftime('%B %d, %Y')}",
            self.styles['Normal']
        ))
        
        story.append(PageBreak())
        
        # Executive Summary
        story.append(Paragraph("Executive Summary", self.styles['CustomHeading']))
        
        summary_text = f"""
        This report presents the results of the SOC2 Type II audit for LLMOptimizer Platform 
        covering the period from {period_start.strftime('%B %d, %Y')} to {period_end.strftime('%B %d, %Y')}.
        
        The audit evaluated the design and operating effectiveness of controls related to the 
        Trust Service Criteria for Security, Availability, Processing Integrity, Confidentiality, 
        and Privacy.
        
        Overall Compliance Score: {assessment_data.get('overall_score', 0):.1f}%
        """
        
        story.append(Paragraph(summary_text, self.styles['CustomBody']))
        story.append(Spacer(1, 0.3*inch))
        
        # Key Findings
        story.append(Paragraph("Key Findings", self.styles['CustomHeading']))
        
        findings_data = [
            ['Category', 'Controls Tested', 'Effective', 'Deficiencies'],
            ['Control Environment', '15', '14', '1'],
            ['Communication & Information', '12', '12', '0'],
            ['Risk Assessment', '10', '9', '1'],
            ['Monitoring Activities', '8', '8', '0'],
            ['Control Activities', '20', '19', '1'],
            ['Logical & Physical Access', '25', '24', '1'],
            ['System Operations', '18', '18', '0'],
            ['Change Management', '10', '9', '1'],
            ['Risk Mitigation', '8', '8', '0']
        ]
        
        findings_table = Table(findings_data, colWidths=[2.5*inch, 1.2*inch, 1*inch, 1*inch])
        findings_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(findings_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Trust Service Criteria Details
        story.append(PageBreak())
        story.append(Paragraph("Trust Service Criteria Assessment", self.styles['CustomHeading']))
        
        for category, controls in assessment_data.get('controls_by_category', {}).items():
            story.append(Paragraph(f"{category}", self.styles['Heading2']))
            
            for control in controls:
                status_color = colors.green if control['status'] == 'effective' else colors.red
                
                control_text = f"""
                <b>{control['id']}: {control['title']}</b><br/>
                Status: <font color="{status_color}">{control['status'].upper()}</font><br/>
                {control['description']}<br/>
                """
                
                story.append(Paragraph(control_text, self.styles['CustomBody']))
                
                if control.get('findings'):
                    story.append(Paragraph("<b>Findings:</b>", self.styles['CustomBody']))
                    findings_list = ListFlowable([
                        ListItem(Paragraph(finding, self.styles['CustomBody']))
                        for finding in control['findings']
                    ], bulletType='bullet')
                    story.append(findings_list)
                
                story.append(Spacer(1, 0.2*inch))
        
        # Testing Procedures
        story.append(PageBreak())
        story.append(Paragraph("Testing Procedures", self.styles['CustomHeading']))
        
        procedures_text = """
        Our testing procedures included:
        
        • Inquiry of relevant personnel
        • Observation of control activities
        • Inspection of documentation and evidence
        • Re-performance of control procedures
        • Analytical procedures and substantive testing
        
        Testing was performed on a sample basis throughout the audit period to evaluate 
        both the design and operating effectiveness of controls.
        """
        
        story.append(Paragraph(procedures_text, self.styles['CustomBody']))
        
        # Management Response
        story.append(PageBreak())
        story.append(Paragraph("Management Response", self.styles['CustomHeading']))
        
        management_response = assessment_data.get('management_response', 
            "Management acknowledges the findings in this report and commits to addressing "
            "identified deficiencies within the agreed-upon timelines."
        )
        
        story.append(Paragraph(management_response, self.styles['CustomBody']))
        
        # Appendices
        story.append(PageBreak())
        story.append(Paragraph("Appendices", self.styles['CustomHeading']))
        
        story.append(Paragraph("Appendix A: Control Matrix", self.styles['Heading2']))
        story.append(Paragraph(
            "A detailed control matrix is provided as a separate Excel file.",
            self.styles['CustomBody']
        ))
        
        story.append(Paragraph("Appendix B: Sample Evidence", self.styles['Heading2']))
        story.append(Paragraph(
            "Sample evidence reviewed during the audit is maintained in the audit workpapers.",
            self.styles['CustomBody']
        ))
        
        # Build PDF
        doc.build(story)
        
        # Generate supporting Excel file
        self._generate_control_matrix_excel(assessment_data, report_id)
        
        logger.info(f"Generated SOC2 audit report: {filename}")
        return str(filename)
    
    def generate_gdpr_compliance_report(self,
                                      assessment_data: Dict[str, Any],
                                      reporting_period: datetime) -> str:
        """Generate GDPR compliance report."""
        report_id = f"GDPR_COMPLIANCE_{reporting_period.strftime('%Y%m%d')}"
        filename = self.reports_dir / f"{report_id}.pdf"
        
        doc = SimpleDocTemplate(str(filename), pagesize=A4)
        story = []
        
        # Title
        story.append(Paragraph(
            "GDPR Compliance Report",
            self.styles['CustomTitle']
        ))
        
        story.append(Paragraph(
            f"Reporting Date: {reporting_period.strftime('%B %d, %Y')}",
            self.styles['Normal']
        ))
        
        story.append(Spacer(1, 0.5*inch))
        
        # Data Protection Officer Statement
        story.append(Paragraph("Data Protection Officer Statement", self.styles['CustomHeading']))
        
        dpo_statement = """
        As the Data Protection Officer for LLMOptimizer, I certify that this report 
        accurately reflects the current state of GDPR compliance for our organization.
        
        We continue to maintain a strong commitment to data protection and privacy, 
        implementing appropriate technical and organizational measures to ensure the 
        rights and freedoms of data subjects are protected.
        """
        
        story.append(Paragraph(dpo_statement, self.styles['CustomBody']))
        story.append(Spacer(1, 0.3*inch))
        
        # Compliance Overview
        story.append(Paragraph("Compliance Overview", self.styles['CustomHeading']))
        
        # Generate compliance chart
        chart_path = self._generate_gdpr_compliance_chart(assessment_data)
        if chart_path:
            story.append(Image(str(chart_path), width=5*inch, height=3*inch))
        
        story.append(Spacer(1, 0.3*inch))
        
        # Data Subject Rights Implementation
        story.append(Paragraph("Data Subject Rights", self.styles['CustomHeading']))
        
        rights_data = [
            ['Right', 'Implementation Status', 'Response Time', 'Requests (30 days)'],
            ['Access (Art. 15)', 'Automated', 'Immediate', '142'],
            ['Rectification (Art. 16)', 'Automated', 'Immediate', '23'],
            ['Erasure (Art. 17)', 'Semi-automated', '48 hours', '87'],
            ['Restriction (Art. 18)', 'Manual', '72 hours', '5'],
            ['Portability (Art. 20)', 'Automated', 'Immediate', '64'],
            ['Object (Art. 21)', 'Semi-automated', '48 hours', '12']
        ]
        
        rights_table = Table(rights_data, colWidths=[2*inch, 1.5*inch, 1.2*inch, 1.3*inch])
        rights_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(rights_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Data Processing Activities
        story.append(PageBreak())
        story.append(Paragraph("Data Processing Activities", self.styles['CustomHeading']))
        
        processing_activities = assessment_data.get('processing_activities', [])
        for activity in processing_activities[:5]:  # Show top 5
            activity_text = f"""
            <b>{activity['name']}</b><br/>
            Purpose: {activity['purpose']}<br/>
            Legal Basis: {activity['legal_basis']}<br/>
            Data Categories: {', '.join(activity['data_categories'])}<br/>
            Retention: {activity['retention_period']}<br/>
            """
            story.append(Paragraph(activity_text, self.styles['CustomBody']))
            story.append(Spacer(1, 0.1*inch))
        
        # Privacy by Design
        story.append(Paragraph("Privacy by Design Implementation", self.styles['CustomHeading']))
        
        pbd_measures = [
            "Data minimization enforced at collection points",
            "Purpose limitation implemented through access controls",
            "Privacy-friendly defaults configured for all user settings",
            "End-to-end encryption for sensitive data",
            "Pseudonymization applied to analytics data",
            "Regular privacy impact assessments conducted"
        ]
        
        pbd_list = ListFlowable([
            ListItem(Paragraph(measure, self.styles['CustomBody']))
            for measure in pbd_measures
        ], bulletType='bullet')
        
        story.append(pbd_list)
        story.append(Spacer(1, 0.3*inch))
        
        # Data Breach Readiness
        story.append(PageBreak())
        story.append(Paragraph("Data Breach Response Readiness", self.styles['CustomHeading']))
        
        breach_readiness = assessment_data.get('breach_readiness', {})
        
        readiness_text = f"""
        Notification Capability: {'✓ Automated' if breach_readiness.get('automated_notification') else '✗ Manual'}<br/>
        72-hour Compliance: {'✓ Yes' if breach_readiness.get('within_72_hours') else '✗ No'}<br/>
        Last Drill: {breach_readiness.get('last_drill_date', 'N/A')}<br/>
        Response Team: {'✓ Established' if breach_readiness.get('response_team') else '✗ Not established'}<br/>
        """
        
        story.append(Paragraph(readiness_text, self.styles['CustomBody']))
        
        # Third Party Compliance
        story.append(Paragraph("Third Party Compliance", self.styles['CustomHeading']))
        
        third_party_data = [
            ['Processor', 'DPA Signed', 'Last Audit', 'Compliance Status'],
            ['AWS', '✓', '2024-01-15', 'Compliant'],
            ['Stripe', '✓', '2024-02-20', 'Compliant'],
            ['SendGrid', '✓', '2024-01-30', 'Compliant'],
            ['Datadog', '✓', '2024-02-10', 'Compliant']
        ]
        
        tp_table = Table(third_party_data, colWidths=[2*inch, 1.2*inch, 1.3*inch, 1.5*inch])
        tp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(tp_table)
        
        # Build PDF
        doc.build(story)
        
        logger.info(f"Generated GDPR compliance report: {filename}")
        return str(filename)
    
    def generate_executive_dashboard(self,
                                   compliance_data: Dict[str, Any],
                                   period: datetime) -> str:
        """Generate executive compliance dashboard."""
        report_id = f"EXEC_DASHBOARD_{period.strftime('%Y%m')}"
        filename = self.reports_dir / f"{report_id}.pdf"
        
        doc = SimpleDocTemplate(str(filename), pagesize=letter)
        story = []
        
        # Title
        story.append(Paragraph(
            "Executive Compliance Dashboard",
            self.styles['CustomTitle']
        ))
        
        story.append(Paragraph(
            f"{period.strftime('%B %Y')}",
            self.styles['Heading2']
        ))
        
        story.append(Spacer(1, 0.5*inch))
        
        # Overall Compliance Score
        overall_score = compliance_data.get('overall_compliance_score', 0)
        score_color = colors.green if overall_score >= 90 else colors.orange if overall_score >= 80 else colors.red
        
        score_text = f"""
        <para align="center">
        <font size="36" color="{score_color}"><b>{overall_score:.1f}%</b></font><br/>
        <font size="14">Overall Compliance Score</font>
        </para>
        """
        
        story.append(Paragraph(score_text, self.styles['Normal']))
        story.append(Spacer(1, 0.5*inch))
        
        # Compliance by Standard
        story.append(Paragraph("Compliance by Standard", self.styles['CustomHeading']))
        
        standards_data = [
            ['Standard', 'Score', 'Status', 'Trend'],
            ['SOC2 Type II', '94.5%', 'Compliant', '↑'],
            ['GDPR', '96.2%', 'Compliant', '→'],
            ['PCI DSS', '91.8%', 'Compliant', '↑'],
            ['ISO 27001', '93.7%', 'Compliant', '↑'],
            ['HIPAA', 'N/A', 'Not Applicable', '-']
        ]
        
        standards_table = Table(standards_data, colWidths=[2.5*inch, 1.2*inch, 1.5*inch, 1*inch])
        standards_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(standards_table)
        story.append(Spacer(1, 0.5*inch))
        
        # Key Metrics
        story.append(Paragraph("Key Compliance Metrics", self.styles['CustomHeading']))
        
        # Generate metrics charts
        metrics_chart = self._generate_metrics_charts(compliance_data)
        if metrics_chart:
            story.append(Image(str(metrics_chart), width=6*inch, height=3*inch))
        
        story.append(PageBreak())
        
        # Risk Heat Map
        story.append(Paragraph("Compliance Risk Heat Map", self.styles['CustomHeading']))
        
        risk_data = [
            ['Area', 'Impact', 'Likelihood', 'Risk Level', 'Mitigation'],
            ['Data Retention', 'High', 'Low', 'Medium', 'Automated deletion implemented'],
            ['Access Control', 'High', 'Medium', 'High', 'MFA enforcement increased'],
            ['Third Party', 'Medium', 'Medium', 'Medium', 'Enhanced vendor assessments'],
            ['Incident Response', 'High', 'Low', 'Medium', 'Regular drills scheduled'],
            ['Training', 'Low', 'High', 'Medium', 'Quarterly training implemented']
        ]
        
        risk_table = Table(risk_data, colWidths=[1.8*inch, 1*inch, 1*inch, 1*inch, 2.2*inch])
        
        # Color code risk levels
        risk_colors = {
            'High': colors.red,
            'Medium': colors.orange,
            'Low': colors.green
        }
        
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        # Apply risk colors
        for i, row in enumerate(risk_data[1:], 1):
            risk_level = row[3]
            if risk_level in risk_colors:
                risk_table.setStyle(TableStyle([
                    ('BACKGROUND', (3, i), (3, i), risk_colors[risk_level])
                ]))
        
        story.append(risk_table)
        story.append(Spacer(1, 0.5*inch))
        
        # Action Items
        story.append(Paragraph("Priority Action Items", self.styles['CustomHeading']))
        
        action_items = compliance_data.get('action_items', [
            {
                'priority': 'Critical',
                'item': 'Complete Q3 access reviews',
                'owner': 'Security Team',
                'due_date': 'Sep 30, 2024'
            },
            {
                'priority': 'High',
                'item': 'Update incident response runbooks',
                'owner': 'DevOps Team',
                'due_date': 'Oct 15, 2024'
            },
            {
                'priority': 'Medium',
                'item': 'Conduct privacy impact assessment for new feature',
                'owner': 'Legal Team',
                'due_date': 'Oct 31, 2024'
            }
        ])
        
        for item in action_items[:5]:  # Show top 5
            priority_color = colors.red if item['priority'] == 'Critical' else colors.orange if item['priority'] == 'High' else colors.black
            
            item_text = f"""
            <font color="{priority_color}"><b>[{item['priority']}]</b></font> {item['item']}<br/>
            Owner: {item['owner']} | Due: {item['due_date']}
            """
            
            story.append(Paragraph(item_text, self.styles['CustomBody']))
            story.append(Spacer(1, 0.1*inch))
        
        # Upcoming Audits
        story.append(PageBreak())
        story.append(Paragraph("Upcoming Audits & Assessments", self.styles['CustomHeading']))
        
        upcoming_audits = [
            ['Audit Type', 'Scheduled Date', 'Auditor', 'Preparation Status'],
            ['SOC2 Type II', 'Dec 1-15, 2024', 'EY', '75% Complete'],
            ['ISO 27001 Surveillance', 'Jan 15, 2025', 'BSI', '60% Complete'],
            ['PCI DSS', 'Feb 1, 2025', 'Internal', '50% Complete'],
            ['GDPR Assessment', 'Mar 1, 2025', 'PwC', '40% Complete']
        ]
        
        audit_table = Table(upcoming_audits, colWidths=[2.2*inch, 1.5*inch, 1.3*inch, 1.5*inch])
        audit_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(audit_table)
        
        # Build PDF
        doc.build(story)
        
        logger.info(f"Generated executive dashboard: {filename}")
        return str(filename)
    
    def generate_evidence_package(self,
                                audit_type: str,
                                controls: List[Dict[str, Any]],
                                period: datetime) -> str:
        """Generate evidence package for auditors."""
        package_id = f"{audit_type}_EVIDENCE_{period.strftime('%Y%m%d')}"
        package_dir = self.reports_dir / package_id
        package_dir.mkdir(exist_ok=True)
        
        # Create index file
        index_file = package_dir / "00_INDEX.md"
        with open(index_file, 'w') as f:
            f.write(f"# {audit_type} Evidence Package\n\n")
            f.write(f"Audit Period: {period.strftime('%B %Y')}\n\n")
            f.write("## Contents\n\n")
            
            for i, control in enumerate(controls, 1):
                f.write(f"{i}. {control['id']} - {control['title']}\n")
                
                # Create control evidence folder
                control_dir = package_dir / f"{i:02d}_{control['id']}"
                control_dir.mkdir(exist_ok=True)
                
                # Create control summary
                summary_file = control_dir / "control_summary.md"
                with open(summary_file, 'w') as cf:
                    cf.write(f"# Control: {control['id']}\n\n")
                    cf.write(f"## {control['title']}\n\n")
                    cf.write(f"**Description:** {control['description']}\n\n")
                    cf.write(f"**Testing Performed:**\n")
                    
                    for test in control.get('tests', []):
                        cf.write(f"- {test['description']}\n")
                        cf.write(f"  - Sample Size: {test.get('sample_size', 'N/A')}\n")
                        cf.write(f"  - Exceptions: {test.get('exceptions', 0)}\n")
                    
                    cf.write(f"\n**Evidence Files:**\n")
                    for evidence in control.get('evidence', []):
                        cf.write(f"- {evidence['filename']}: {evidence['description']}\n")
                
                # Copy evidence files (in real implementation)
                # self._copy_evidence_files(control['evidence'], control_dir)
        
        # Create evidence matrix Excel
        self._create_evidence_matrix(controls, package_dir / "evidence_matrix.xlsx")
        
        # Create testing workpapers
        self._create_testing_workpapers(controls, package_dir / "testing_workpapers.xlsx")
        
        # Zip the package
        import shutil
        zip_file = self.reports_dir / f"{package_id}.zip"
        shutil.make_archive(str(zip_file.with_suffix('')), 'zip', package_dir)
        
        logger.info(f"Generated evidence package: {zip_file}")
        return str(zip_file)
    
    def _generate_control_matrix_excel(self, assessment_data: Dict[str, Any], report_id: str):
        """Generate detailed control matrix in Excel format."""
        filename = self.reports_dir / f"{report_id}_control_matrix.xlsx"
        
        workbook = xlsxwriter.Workbook(str(filename))
        
        # Formats
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#34495e',
            'font_color': 'white',
            'border': 1
        })
        
        cell_format = workbook.add_format({
            'text_wrap': True,
            'valign': 'top',
            'border': 1
        })
        
        effective_format = workbook.add_format({
            'text_wrap': True,
            'valign': 'top',
            'border': 1,
            'fg_color': '#2ecc71'
        })
        
        ineffective_format = workbook.add_format({
            'text_wrap': True,
            'valign': 'top',
            'border': 1,
            'fg_color': '#e74c3c'
        })
        
        # Control Matrix worksheet
        worksheet = workbook.add_worksheet('Control Matrix')
        
        # Headers
        headers = [
            'Control ID', 'Control Title', 'Category', 'Description',
            'Control Type', 'Frequency', 'Responsible Party', 
            'Testing Procedure', 'Sample Size', 'Exceptions',
            'Status', 'Remediation Required'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Data
        row = 1
        for control in assessment_data.get('all_controls', []):
            worksheet.write(row, 0, control['id'], cell_format)
            worksheet.write(row, 1, control['title'], cell_format)
            worksheet.write(row, 2, control['category'], cell_format)
            worksheet.write(row, 3, control['description'], cell_format)
            worksheet.write(row, 4, control.get('type', 'Preventive'), cell_format)
            worksheet.write(row, 5, control.get('frequency', 'Continuous'), cell_format)
            worksheet.write(row, 6, control.get('responsible_party', 'IT Security'), cell_format)
            worksheet.write(row, 7, control.get('testing_procedure', 'Review and test'), cell_format)
            worksheet.write(row, 8, control.get('sample_size', 25), cell_format)
            worksheet.write(row, 9, control.get('exceptions', 0), cell_format)
            
            status_format = effective_format if control['status'] == 'effective' else ineffective_format
            worksheet.write(row, 10, control['status'], status_format)
            
            remediation = 'Yes' if control['status'] != 'effective' else 'No'
            worksheet.write(row, 11, remediation, cell_format)
            
            row += 1
        
        # Adjust column widths
        worksheet.set_column('A:A', 12)
        worksheet.set_column('B:B', 30)
        worksheet.set_column('C:C', 20)
        worksheet.set_column('D:D', 50)
        worksheet.set_column('E:L', 15)
        
        # Risk Assessment worksheet
        risk_worksheet = workbook.add_worksheet('Risk Assessment')
        
        risk_headers = [
            'Risk ID', 'Risk Description', 'Impact', 'Likelihood',
            'Inherent Risk', 'Control ID', 'Control Effectiveness',
            'Residual Risk', 'Action Required'
        ]
        
        for col, header in enumerate(risk_headers):
            risk_worksheet.write(0, col, header, header_format)
        
        # Add risk data (simplified example)
        risks = [
            {
                'id': 'R001',
                'description': 'Unauthorized access to sensitive data',
                'impact': 'High',
                'likelihood': 'Medium',
                'inherent_risk': 'High',
                'control_id': 'CC6.1',
                'control_effectiveness': 'Effective',
                'residual_risk': 'Low'
            },
            {
                'id': 'R002',
                'description': 'Data breach due to weak encryption',
                'impact': 'High',
                'likelihood': 'Low',
                'inherent_risk': 'Medium',
                'control_id': 'CC6.7',
                'control_effectiveness': 'Effective',
                'residual_risk': 'Low'
            }
        ]
        
        row = 1
        for risk in risks:
            risk_worksheet.write(row, 0, risk['id'], cell_format)
            risk_worksheet.write(row, 1, risk['description'], cell_format)
            risk_worksheet.write(row, 2, risk['impact'], cell_format)
            risk_worksheet.write(row, 3, risk['likelihood'], cell_format)
            risk_worksheet.write(row, 4, risk['inherent_risk'], cell_format)
            risk_worksheet.write(row, 5, risk['control_id'], cell_format)
            risk_worksheet.write(row, 6, risk['control_effectiveness'], cell_format)
            risk_worksheet.write(row, 7, risk['residual_risk'], cell_format)
            risk_worksheet.write(row, 8, 'Monitor' if risk['residual_risk'] == 'Low' else 'Mitigate', cell_format)
            row += 1
        
        workbook.close()
    
    def _generate_gdpr_compliance_chart(self, assessment_data: Dict[str, Any]) -> Optional[Path]:
        """Generate GDPR compliance visualization chart."""
        try:
            plt.figure(figsize=(10, 6))
            
            # Sample data - would come from assessment_data
            categories = ['Data Subject Rights', 'Lawful Basis', 'Security', 
                         'Accountability', 'Privacy by Design', 'Third Parties']
            scores = [95, 88, 92, 85, 90, 87]
            
            # Create bar chart
            bars = plt.bar(categories, scores, color=['#2ecc71' if s >= 90 else '#f39c12' if s >= 80 else '#e74c3c' for s in scores])
            
            # Add value labels on bars
            for bar, score in zip(bars, scores):
                plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                        f'{score}%', ha='center', va='bottom')
            
            plt.title('GDPR Compliance by Category', fontsize=16, fontweight='bold')
            plt.ylabel('Compliance Score (%)', fontsize=12)
            plt.ylim(0, 105)
            plt.xticks(rotation=45, ha='right')
            
            # Add target line
            plt.axhline(y=90, color='r', linestyle='--', label='Target (90%)')
            plt.legend()
            
            plt.tight_layout()
            
            # Save chart
            chart_path = self.reports_dir / 'gdpr_compliance_chart.png'
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            return chart_path
            
        except Exception as e:
            logger.error(f"Error generating GDPR chart: {e}")
            return None
    
    def _generate_metrics_charts(self, compliance_data: Dict[str, Any]) -> Optional[Path]:
        """Generate compliance metrics charts."""
        try:
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 8))
            
            # Chart 1: Compliance Trend
            months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
            scores = [87, 89, 91, 90, 93, 94.5]
            
            ax1.plot(months, scores, marker='o', linewidth=2, markersize=8)
            ax1.set_title('Compliance Score Trend', fontweight='bold')
            ax1.set_ylabel('Score (%)')
            ax1.set_ylim(80, 100)
            ax1.grid(True, alpha=0.3)
            
            # Chart 2: Controls by Status
            status_labels = ['Effective', 'Partially Effective', 'Ineffective', 'Not Tested']
            status_values = [115, 8, 3, 4]
            colors_pie = ['#2ecc71', '#f39c12', '#e74c3c', '#95a5a6']
            
            ax2.pie(status_values, labels=status_labels, colors=colors_pie, autopct='%1.1f%%')
            ax2.set_title('Controls by Status', fontweight='bold')
            
            # Chart 3: Audit Findings by Category
            categories = ['Access Control', 'Change Mgmt', 'Operations', 'Risk']
            findings = [2, 1, 0, 1]
            
            ax3.bar(categories, findings, color='#3498db')
            ax3.set_title('Audit Findings by Category', fontweight='bold')
            ax3.set_ylabel('Number of Findings')
            ax3.set_ylim(0, 5)
            
            # Chart 4: Remediation Progress
            items = ['Q1 Items', 'Q2 Items', 'Q3 Items', 'Q4 Items']
            completed = [100, 95, 75, 20]
            
            ax4.barh(items, completed, color='#9b59b6')
            ax4.set_title('Remediation Progress', fontweight='bold')
            ax4.set_xlabel('Completion (%)')
            ax4.set_xlim(0, 100)
            
            # Add percentage labels
            for i, v in enumerate(completed):
                ax4.text(v + 1, i, f'{v}%', va='center')
            
            plt.tight_layout()
            
            # Save chart
            chart_path = self.reports_dir / 'compliance_metrics.png'
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            return chart_path
            
        except Exception as e:
            logger.error(f"Error generating metrics charts: {e}")
            return None
    
    def _create_evidence_matrix(self, controls: List[Dict[str, Any]], filename: Path):
        """Create evidence matrix Excel file."""
        workbook = xlsxwriter.Workbook(str(filename))
        worksheet = workbook.add_worksheet('Evidence Matrix')
        
        # Headers
        headers = [
            'Control ID', 'Control Description', 'Evidence Type',
            'Evidence Description', 'Location', 'Review Date', 'Reviewer'
        ]
        
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'border': 1
        })
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Data
        row = 1
        for control in controls:
            for evidence in control.get('evidence', []):
                worksheet.write(row, 0, control['id'])
                worksheet.write(row, 1, control['title'])
                worksheet.write(row, 2, evidence.get('type', 'Screenshot'))
                worksheet.write(row, 3, evidence.get('description', ''))
                worksheet.write(row, 4, evidence.get('location', ''))
                worksheet.write(row, 5, evidence.get('review_date', ''))
                worksheet.write(row, 6, evidence.get('reviewer', ''))
                row += 1
        
        # Auto-fit columns
        worksheet.set_column('A:A', 12)
        worksheet.set_column('B:B', 40)
        worksheet.set_column('C:G', 20)
        
        workbook.close()
    
    def _create_testing_workpapers(self, controls: List[Dict[str, Any]], filename: Path):
        """Create testing workpapers Excel file."""
        workbook = xlsxwriter.Workbook(str(filename))
        
        # Summary sheet
        summary_sheet = workbook.add_worksheet('Summary')
        
        # Individual control sheets
        for control in controls[:10]:  # Limit to first 10 for example
            sheet_name = f"{control['id']}"[:31]  # Excel sheet name limit
            worksheet = workbook.add_worksheet(sheet_name)
            
            # Control information
            worksheet.write('A1', 'Control ID:', workbook.add_format({'bold': True}))
            worksheet.write('B1', control['id'])
            
            worksheet.write('A2', 'Control Title:', workbook.add_format({'bold': True}))
            worksheet.write('B2', control['title'])
            
            worksheet.write('A4', 'Testing Procedures:', workbook.add_format({'bold': True}))
            
            # Testing steps
            row = 5
            for i, test in enumerate(control.get('tests', []), 1):
                worksheet.write(row, 0, f"Step {i}:")
                worksheet.write(row, 1, test.get('procedure', ''))
                worksheet.write(row + 1, 1, f"Result: {test.get('result', 'Pending')}")
                row += 3
        
        workbook.close()


class AuditTrailLogger:
    """Log all compliance-related activities for audit trail."""
    
    def __init__(self):
        self.log_file = Path('compliance/audit_trail.jsonl')
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log_activity(self, activity_type: str, details: Dict[str, Any]):
        """Log a compliance activity."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'activity_type': activity_type,
            'details': details,
            'user': os.getenv('USER', 'system'),
            'session_id': os.getenv('SESSION_ID', 'unknown')
        }
        
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    
    def log_assessment(self, standard: str, score: float, findings: int):
        """Log compliance assessment."""
        self.log_activity('compliance_assessment', {
            'standard': standard,
            'score': score,
            'findings': findings
        })
    
    def log_control_test(self, control_id: str, result: str, evidence: List[str]):
        """Log control testing."""
        self.log_activity('control_test', {
            'control_id': control_id,
            'result': result,
            'evidence_files': evidence
        })
    
    def log_remediation(self, finding_id: str, action: str, status: str):
        """Log remediation activity."""
        self.log_activity('remediation', {
            'finding_id': finding_id,
            'action': action,
            'status': status
        })
    
    def log_policy_update(self, policy_id: str, changes: Dict[str, Any]):
        """Log policy updates."""
        self.log_activity('policy_update', {
            'policy_id': policy_id,
            'changes': changes
        })
    
    def log_access_review(self, review_type: str, users_reviewed: int, changes_made: int):
        """Log access review activity."""
        self.log_activity('access_review', {
            'review_type': review_type,
            'users_reviewed': users_reviewed,
            'changes_made': changes_made
        })
    
    def get_audit_trail(self, start_date: datetime, end_date: datetime,
                       activity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve audit trail entries."""
        entries = []
        
        with open(self.log_file, 'r') as f:
            for line in f:
                entry = json.loads(line)
                entry_date = datetime.fromisoformat(entry['timestamp'])
                
                if start_date <= entry_date <= end_date:
                    if activity_type is None or entry['activity_type'] == activity_type:
                        entries.append(entry)
        
        return entries


if __name__ == "__main__":
    # Example usage
    generator = AuditReportGenerator()
    
    # Generate SOC2 audit report
    assessment_data = {
        'overall_score': 94.5,
        'controls_by_category': {
            'CC1: Control Environment': [
                {
                    'id': 'CC1.1',
                    'title': 'Organizational Structure',
                    'description': 'The entity has defined organizational structures',
                    'status': 'effective',
                    'findings': []
                }
            ]
        },
        'all_controls': [],
        'management_response': 'Management acknowledges the findings...'
    }
    
    soc2_report = generator.generate_soc2_audit_report(
        assessment_data,
        datetime.now() - timedelta(days=90),
        datetime.now()
    )
    
    print(f"Generated SOC2 report: {soc2_report}")
    
    # Generate executive dashboard
    compliance_data = {
        'overall_compliance_score': 93.5,
        'standards': {
            'SOC2': 94.5,
            'GDPR': 96.2,
            'PCI DSS': 91.8
        },
        'action_items': []
    }
    
    dashboard = generator.generate_executive_dashboard(
        compliance_data,
        datetime.now()
    )
    
    print(f"Generated executive dashboard: {dashboard}")