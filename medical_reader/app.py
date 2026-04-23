"""
Streamlit Dashboard: Medical Underwriting Agent

Interactive interface for processing medical PDFs through the LangGraph workflow.

Features:
- Upload or select test PDFs
- LangGraph orchestration with HITL checkpointing
- Human-in-the-loop review queue
- Real-time extraction, pricing, and review
- Full audit trail for compliance
"""

import streamlit as st
import sys
import os
from pathlib import Path
import json
from datetime import datetime

from medical_reader.state import UnderwritingState
from medical_reader.graph import run_case, submit_review


def format_confidence(confidence: float) -> str:
    """Format confidence score with color coding."""
    pct = confidence * 100
    if confidence >= 0.8:
        return f"🟢 {pct:.0f}%"
    elif confidence >= 0.6:
        return f"🟡 {pct:.0f}%"
    else:
        return f"🔴 {pct:.0f}%"


def format_risk_level(risk_level) -> str:
    """Format risk level with color coding."""
    colors = {
        "low": "🟢",
        "medium": "🟡",
        "high": "🔴",
        "decline": "🚫",
    }
    return f"{colors.get(risk_level, '❓')} {risk_level.upper()}"


def display_case_details(state: UnderwritingState, show_edit_controls=False):
    """Display extracted medical data, risk assessment, and audit trail.

    Args:
        state: UnderwritingState to display
        show_edit_controls: If True, show edit/action buttons
    """

    # Status banner
    status_colors = {
        "pending": "🔵",
        "intake": "🟡",
        "pricing": "🟠",
        "review": "🟣",
        "approved": "🟢",
        "declined": "🔴",
        "error": "⚫",
    }
    status_emoji = status_colors.get(state.status, "❓")
    st.success(f"{status_emoji} Status: **{state.status.upper()}**")

    if state.errors:
        for error in state.errors:
            st.warning(f"⚠️ {error}")

    # Main metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Risk Level", format_risk_level(state.risk_level.value))
    with col2:
        st.metric("Risk Score", f"{state.risk_score:.1f}/100")
    with col3:
        st.metric("Overall Confidence", format_confidence(state.overall_confidence))
    with col4:
        st.metric("Final Premium", f"${state.actuarial.final_premium:,.0f}")

    st.divider()

    # Extracted Medical Data
    st.header("📋 Extracted Medical Data")
    extracted = state.extracted_data
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Demographics")
        st.write(f"**Age:** {extracted.age or 'N/A'}")
        st.write(f"**Gender:** {extracted.gender or 'N/A'}")

        st.subheader("Vitals")
        st.write(f"**BMI:** {extracted.bmi or 'N/A'}")
        st.write(f"**Blood Pressure:** {extracted.blood_pressure_systolic or 'N/A'}/{extracted.blood_pressure_diastolic or 'N/A'} mmHg")

    with col2:
        st.subheader("Lifestyle")
        st.write(f"**Smoker:** {'Yes' if extracted.smoker else 'No' if extracted.smoker is not None else 'Unknown'}")
        st.write(f"**Alcohol Use:** {extracted.alcohol_use or 'Unknown'}")

        st.subheader("Medical Conditions")
        st.write(f"**Diabetes:** {'Yes' if extracted.diabetes else 'No' if extracted.diabetes is not None else 'Unknown'}")
        st.write(f"**Hypertension:** {'Yes' if extracted.hypertension else 'No' if extracted.hypertension is not None else 'Unknown'}")
        st.write(f"**Hyperlipidemia:** {'Yes' if extracted.hyperlipidemia else 'No' if extracted.hyperlipidemia is not None else 'Unknown'}")
        st.write(f"**Family CHD:** {'Yes' if extracted.family_history_chd else 'No' if extracted.family_history_chd is not None else 'Unknown'}")

    # Confidence scores table
    if extracted.confidence_scores:
        st.subheader("Extraction Confidence")
        confidence_data = []
        for field, conf in sorted(extracted.confidence_scores.items()):
            confidence_data.append(
                {
                    "Field": field,
                    "Confidence": f"{conf:.0%}",
                    "Status": "🟢 High" if conf >= 0.8 else "🟡 Medium" if conf >= 0.6 else "🔴 Low",
                }
            )
        st.dataframe(confidence_data, use_container_width=True, hide_index=True)

    st.divider()

    # Actuarial Calculation
    st.header("💰 Actuarial Calculation")
    col1, col2 = st.columns(2)

    with col1:
        st.metric("Base Frequency", f"{state.actuarial.base_frequency:.3f} claims/year")
        st.metric("Frequency Score", f"{state.actuarial.frequency_score:.2f}x")
        st.metric("Adjusted Frequency", f"{state.actuarial.adjusted_frequency:.4f}")

    with col2:
        st.metric("Base Severity", f"${state.actuarial.base_severity:,.0f}")
        st.metric("Severity Score", f"{state.actuarial.severity_score:.2f}x")
        st.metric("Adjusted Severity", f"${state.actuarial.adjusted_severity:,.0f}")

    st.info(f"📝 {state.actuarial.calculation_notes}")

    st.divider()

    # Review Notes
    st.header("👥 Human Review")
    if state.review.required:
        st.warning(
            f"⚠️ **Review Required** — {state.review.reason or 'No specific reason provided'}"
        )
        if show_edit_controls:
            st.info("👉 This case is awaiting reviewer decision. Go to the **Review Queue** tab to approve or decline.")
    else:
        st.success("✅ **No human review required** (Auto-approved via STP)")

    st.divider()

    # Audit Trail (for compliance)
    st.header("📜 Audit Trail (Compliance)")
    with st.expander(f"View All {len(state.audit_trail)} Audit Entries"):
        audit_lines = []
        for entry in state.audit_trail:
            timestamp = entry.timestamp.isoformat()
            audit_lines.append(f"**[{timestamp}] {entry.node}/{entry.action}** (confidence: {entry.confidence:.2f})")
            for key, value in entry.details.items():
                audit_lines.append(f"  • {key}: {value}")
            audit_lines.append("")
        st.code("\n".join(audit_lines), language="text")

    # Download audit report
    audit_report = state.to_audit_report()
    button_suffix = "edit" if show_edit_controls else "view"
    st.download_button(
        label="📥 Download Audit Report",
        data=audit_report,
        file_name=f"{state.case_id}_audit_report.txt",
        mime="text/plain",
        key=f"audit_report_{state.case_id}_{button_suffix}",
    )

    # Export state as JSON
    summary = state.to_summary()
    st.download_button(
        label="💾 Export Case Summary (JSON)",
        data=json.dumps(summary, indent=2, default=str),
        file_name=f"{state.case_id}_summary.json",
        mime="application/json",
        key=f"case_summary_{state.case_id}_{button_suffix}",
    )


def main():
    st.set_page_config(
        page_title="Medical Underwriting Agent",
        page_icon="🏥",
        layout="wide",
    )

    st.title("🏥 Medical Underwriting Agent")
    st.markdown(
        "LangGraph-orchestrated medical risk assessment with human-in-the-loop review | "
        "[Phase 3: Command Center](https://github.com/trc-dac/dac-uw-agent)"
    )
    st.divider()

    # Initialize session state
    if "cases" not in st.session_state:
        st.session_state.cases = {}  # Dict[case_id, UnderwritingState]

    # Sidebar: PDF Selection for new cases
    with st.sidebar:
        st.header("📄 New Case Input")

        # Test data directory
        test_data_dir = Path(__file__).parent / "test_data"
        test_files = list(test_data_dir.glob("*.pdf")) if test_data_dir.exists() else []

        input_mode = st.radio("Select Input Method:", ["Test PDF", "Upload PDF"])

        pdf_path = None
        case_id = f"CASE-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        if input_mode == "Test PDF":
            if test_files:
                selected = st.selectbox(
                    "Choose Test PDF:",
                    options=test_files,
                    format_func=lambda x: x.name,
                )
                pdf_path = str(selected)
            else:
                st.error("No test PDFs found in test_data/")

        else:
            uploaded = st.file_uploader("Upload Medical PDF", type=["pdf"])
            if uploaded:
                # Save uploaded file temporarily
                temp_path = test_data_dir / f"upload_{datetime.now().isoformat()}.pdf"
                temp_path.parent.mkdir(exist_ok=True)
                with open(temp_path, "wb") as f:
                    f.write(uploaded.getbuffer())
                pdf_path = str(temp_path)

        if pdf_path:
            st.info(f"📌 Case ID: `{case_id}`")

            def on_run_workflow():
                st.session_state.run_workflow = True
                st.session_state.pdf_path = pdf_path
                st.session_state.case_id = case_id

            st.button("▶️ Run Workflow", key="run_workflow_btn", use_container_width=True, on_click=on_run_workflow)

    # Main content: 3-tab layout
    tab1, tab2, tab3 = st.tabs(["New Case", "Review Queue", "Case History"])

    # ========== TAB 1: NEW CASE ==========
    with tab1:
        # Execute workflow if requested
        if "run_workflow" in st.session_state and st.session_state.run_workflow:
            with st.spinner("Processing medical document through underwriting workflow..."):
                try:
                    state = run_case(
                        st.session_state.case_id,
                        st.session_state.pdf_path,
                    )
                    st.session_state.cases[st.session_state.case_id] = state
                    st.session_state.run_workflow = False
                except Exception as e:
                    st.error(f"❌ Workflow error: {str(e)}")
                    st.session_state.run_workflow = False

        # Display case if one was just processed
        if st.session_state.get("case_id") and st.session_state.case_id in st.session_state.cases:
            state = st.session_state.cases[st.session_state.case_id]
            display_case_details(state, show_edit_controls=True)

    # ========== TAB 2: REVIEW QUEUE ==========
    with tab2:
        st.header("👥 Review Queue")

        # Find all cases awaiting review
        pending_cases = [
            (cid, case) for cid, case in st.session_state.cases.items()
            if case.status == "review"
        ]

        if not pending_cases:
            st.info("No cases awaiting human review.")
        else:
            st.success(f"**{len(pending_cases)} case(s) awaiting review**")

            for case_id, case in pending_cases:
                with st.expander(
                    f"**{case_id}** | Risk: {format_risk_level(case.risk_level.value)} | Score: {case.risk_score:.1f}"
                ):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.subheader("Case Summary")
                        st.write(f"**Applicant Age:** {case.extracted_data.age or 'N/A'}")
                        st.write(f"**BMI:** {case.extracted_data.bmi or 'N/A'}")
                        st.write(f"**Blood Pressure:** {case.extracted_data.blood_pressure_systolic or 'N/A'}/{case.extracted_data.blood_pressure_diastolic or 'N/A'}")
                        st.write(f"**Risk Score:** {case.risk_score:.1f}/100")
                        st.write(f"**Proposed Premium:** ${case.actuarial.final_premium:,.0f}")

                    with col2:
                        st.subheader("Review Details")
                        st.write(f"**Risk Level:** {case.risk_level.value.upper()}")
                        st.write(f"**Extraction Confidence:** {format_confidence(case.overall_confidence)}")
                        st.write(f"**Reason for Review:**")
                        st.caption(case.review.reason or "No specific reason provided")

                    st.divider()

                    # Review decision form
                    st.subheader("Reviewer Decision")

                    col1, col2 = st.columns(2)
                    with col1:
                        approved = st.radio(
                            "Decision:",
                            options=[True, False],
                            format_func=lambda x: "✅ Approve" if x else "❌ Decline",
                            key=f"decision_{case_id}",
                        )

                    reviewer_id = st.text_input(
                        "Your ID (optional)",
                        value="underwriter",
                        key=f"reviewer_id_{case_id}",
                    )

                    notes = st.text_area(
                        "Review Notes",
                        placeholder="Enter any notes about this decision...",
                        key=f"notes_{case_id}",
                        height=100,
                    )

                    if st.button(
                        "✓ Submit Review Decision",
                        key=f"submit_{case_id}",
                        use_container_width=True,
                        type="primary",
                    ):
                        with st.spinner(f"Processing review for {case_id}..."):
                            try:
                                updated_state = submit_review(
                                    case_id,
                                    approved,
                                    notes,
                                    reviewer_id,
                                )
                                st.session_state.cases[case_id] = updated_state
                                st.success(f"✅ Review submitted! Case status: **{updated_state.status.upper()}**")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error submitting review: {str(e)}")

    # ========== TAB 3: CASE HISTORY ==========
    with tab3:
        st.header("📊 Case History")

        if not st.session_state.cases:
            st.info("No cases processed yet.")
        else:
            # Summary table
            history_data = []
            for case_id, case in st.session_state.cases.items():
                history_data.append({
                    "Case ID": case_id,
                    "Status": case.status.upper(),
                    "Risk Level": case.risk_level.value.upper(),
                    "Risk Score": f"{case.risk_score:.1f}",
                    "Premium": f"${case.actuarial.final_premium:,.0f}",
                    "Reviewer": case.review.reviewer_id or "—",
                    "Created": case.created_at.strftime("%Y-%m-%d %H:%M"),
                })

            st.dataframe(
                history_data,
                use_container_width=True,
                hide_index=True,
            )

            st.divider()

            # Detailed view
            st.subheader("Detailed Case View")
            selected_case_id = st.selectbox(
                "Select a case to view details:",
                options=list(st.session_state.cases.keys()),
                format_func=lambda cid: f"{cid} ({st.session_state.cases[cid].status})",
            )

            if selected_case_id:
                display_case_details(
                    st.session_state.cases[selected_case_id],
                    show_edit_controls=False,
                )


if __name__ == "__main__":
    main()
