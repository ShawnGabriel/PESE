"""
PESE Dashboard — Streamlit-based BI layer for the LP prospect pipeline.
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from pese.database import Contact, Organization, RunLog, get_session, init_db

TIER_COLORS = {
    "PRIORITY CLOSE": "#22c55e",
    "STRONG FIT": "#3b82f6",
    "MODERATE FIT": "#eab308",
    "WEAK FIT": "#ef4444",
    "UNSCORED": "#9ca3af",
}

st.set_page_config(
    page_title="PESE — LP Prospect Pipeline",
    page_icon="📊",
    layout="wide",
)


@st.cache_data(ttl=30)
def load_data():
    init_db()
    session = get_session()

    contacts = session.query(Contact).all()
    latest_run = session.query(RunLog).order_by(RunLog.id.desc()).first()

    rows = []
    for c in contacts:
        org = c.organization
        rows.append({
            "Contact": c.name,
            "Organization": org.name if org else "",
            "Org Type": org.org_type if org else "",
            "Role": c.role or "",
            "Email": c.email or "",
            "Region": c.region or "",
            "Contact Status": c.contact_status or "",
            "Relationship Depth": c.relationship_depth,
            "Sector Fit": org.sector_fit_score if org else None,
            "Halo Value": org.halo_score if org else None,
            "Emerging Mgr Fit": org.emerging_manager_score if org else None,
            "Composite Score": c.composite_score,
            "Tier": c.tier or "UNSCORED",
            "AUM ($M)": org.aum_millions if org else None,
            "Check Size Low ($M)": org.estimated_check_size_low if org else None,
            "Check Size High ($M)": org.estimated_check_size_high if org else None,
            "Is LP": org.is_lp if org else None,
            "Confidence": org.confidence if org else None,
            # D1 sub-components
            "D1a LP Status": org.d1_a_lp_status if org else None,
            "D1a Reasoning": org.d1_a_reasoning if org else "",
            "D1b Credit": org.d1_b_credit if org else None,
            "D1b Reasoning": org.d1_b_reasoning if org else "",
            "D1c Sustainability": org.d1_c_sustainability if org else None,
            "D1c Reasoning": org.d1_c_reasoning if org else "",
            "Sector Reasoning": org.sector_fit_reasoning if org else "",
            "D1 Confidence": org.d1_confidence if org else "",
            # D3 sub-components
            "D3a Brand": org.d3_a_brand if org else None,
            "D3a Reasoning": org.d3_a_reasoning if org else "",
            "D3b Network": org.d3_b_network if org else None,
            "D3b Reasoning": org.d3_b_reasoning if org else "",
            "D3c Specificity": org.d3_c_specificity if org else None,
            "D3c Reasoning": org.d3_c_reasoning if org else "",
            "Halo Reasoning": org.halo_reasoning if org else "",
            "D3 Confidence": org.d3_confidence if org else "",
            # D4 sub-components
            "D4a Structural": org.d4_a_structural if org else None,
            "D4a Reasoning": org.d4_a_reasoning if org else "",
            "D4b Track Record": org.d4_b_track_record if org else None,
            "D4b Reasoning": org.d4_b_reasoning if org else "",
            "D4c Check Size": org.d4_c_checksize if org else None,
            "D4c Reasoning": org.d4_c_reasoning if org else "",
            "D4 Red Flags": org.d4_red_flags if org else "",
            "Emerging Reasoning": org.emerging_manager_reasoning if org else "",
            "D4 Confidence": org.d4_confidence if org else "",
        })

    session.close()
    return pd.DataFrame(rows), latest_run


def _score_bar(label: str, score, weight: str, reasoning: str):
    """Render a single sub-component score as a metric + progress bar + reasoning."""
    col_l, col_r = st.columns([1, 3])
    with col_l:
        display = f"{score:.1f}" if pd.notna(score) else "—"
        st.metric(f"{label} ({weight})", display)
    with col_r:
        if pd.notna(score):
            st.progress(min(score / 10.0, 1.0))
        if reasoning:
            st.caption(reasoning)


def main():
    st.title("PESE — LP Prospect Enrichment & Scoring Engine")
    st.caption("PaceZero Capital Partners | Fund II Fundraising Pipeline")

    df, latest_run = load_data()

    if df.empty:
        st.warning("No data found. Run the pipeline first: `python main.py run`")
        return

    # --- Run stats ---
    if latest_run:
        cols = st.columns(5)
        cols[0].metric("Contacts", len(df))
        cols[1].metric("Organizations", df["Organization"].nunique())
        scored = df[df["Tier"] != "UNSCORED"]
        cols[2].metric("Scored", len(scored))
        cols[3].metric("Run Cost", f"${latest_run.total_cost_usd:.4f}" if latest_run.total_cost_usd else "—")
        cols[4].metric("Status", latest_run.status.upper() if latest_run.status else "—")

    st.divider()

    # --- Filters ---
    with st.expander("Filters", expanded=True):
        filter_cols = st.columns(4)
        with filter_cols[0]:
            tier_filter = st.multiselect(
                "Tier",
                options=list(TIER_COLORS.keys()),
                default=["PRIORITY CLOSE", "STRONG FIT", "MODERATE FIT"],
            )
        with filter_cols[1]:
            org_types = sorted(df["Org Type"].dropna().unique().tolist())
            type_filter = st.multiselect("Org Type", options=org_types, default=org_types)
        with filter_cols[2]:
            status_opts = sorted(df["Contact Status"].dropna().unique().tolist())
            status_filter = st.multiselect("Contact Status", options=status_opts, default=status_opts)
        with filter_cols[3]:
            region_opts = sorted(df["Region"].dropna().unique().tolist())
            region_filter = st.multiselect("Region", options=region_opts, default=region_opts)

    filtered = df[
        (df["Tier"].isin(tier_filter))
        & (df["Org Type"].isin(type_filter))
        & (df["Contact Status"].isin(status_filter))
        & (df["Region"].isin(region_filter))
    ]

    # --- Pipeline overview charts ---
    st.subheader("Pipeline Overview")
    chart_cols = st.columns(2)

    with chart_cols[0]:
        tier_counts = filtered["Tier"].value_counts().reindex(list(TIER_COLORS.keys()), fill_value=0)
        fig_tier = px.bar(
            x=tier_counts.index, y=tier_counts.values,
            color=tier_counts.index, color_discrete_map=TIER_COLORS,
            labels={"x": "Tier", "y": "Count"}, title="Prospects by Tier",
        )
        fig_tier.update_layout(showlegend=False)
        st.plotly_chart(fig_tier, use_container_width=True)

    with chart_cols[1]:
        type_tier = filtered.groupby(["Org Type", "Tier"]).size().reset_index(name="Count")
        fig_type = px.bar(
            type_tier, x="Org Type", y="Count", color="Tier",
            color_discrete_map=TIER_COLORS, title="Tier Distribution by Org Type", barmode="stack",
        )
        st.plotly_chart(fig_type, use_container_width=True)

    # --- Score scatter ---
    st.subheader("Score Analysis")
    scatter_cols = st.columns(2)

    with scatter_cols[0]:
        scored_df = filtered.dropna(subset=["Sector Fit", "Relationship Depth"])
        if not scored_df.empty:
            fig = px.scatter(
                scored_df, x="Sector Fit", y="Relationship Depth", color="Tier",
                size="Composite Score", hover_data=["Contact", "Organization", "Composite Score"],
                title="Sector Fit vs Relationship Depth", color_discrete_map=TIER_COLORS,
            )
            st.plotly_chart(fig, use_container_width=True)

    with scatter_cols[1]:
        scored_df2 = filtered.dropna(subset=["Halo Value", "Emerging Mgr Fit"])
        if not scored_df2.empty:
            fig2 = px.scatter(
                scored_df2, x="Halo Value", y="Emerging Mgr Fit", color="Tier",
                size="Composite Score", hover_data=["Contact", "Organization", "Composite Score"],
                title="Halo Value vs Emerging Manager Fit", color_discrete_map=TIER_COLORS,
            )
            st.plotly_chart(fig2, use_container_width=True)

    # --- Main table ---
    st.subheader("Prospect Pipeline")
    display_cols = [
        "Contact", "Organization", "Org Type", "Role",
        "Contact Status", "Composite Score", "Tier",
        "Sector Fit", "Relationship Depth", "Halo Value", "Emerging Mgr Fit",
        "AUM ($M)", "Check Size Low ($M)", "Check Size High ($M)", "Confidence",
    ]
    st.dataframe(
        filtered[display_cols].sort_values("Composite Score", ascending=False),
        use_container_width=True, height=500,
        column_config={
            "Composite Score": st.column_config.NumberColumn(format="%.2f"),
            "Sector Fit": st.column_config.NumberColumn(format="%.1f"),
            "Relationship Depth": st.column_config.NumberColumn(format="%.1f"),
            "Halo Value": st.column_config.NumberColumn(format="%.1f"),
            "Emerging Mgr Fit": st.column_config.NumberColumn(format="%.1f"),
            "AUM ($M)": st.column_config.NumberColumn(format="$%.0f"),
            "Check Size Low ($M)": st.column_config.NumberColumn(format="$%.2f"),
            "Check Size High ($M)": st.column_config.NumberColumn(format="$%.2f"),
        },
    )

    # --- Detail view with sub-component breakdown ---
    st.subheader("Prospect Detail")
    orgs_list = sorted(filtered["Organization"].unique().tolist())
    selected_org = st.selectbox("Select an organization", options=orgs_list)

    if selected_org:
        org_rows = filtered[filtered["Organization"] == selected_org]
        if not org_rows.empty:
            row = org_rows.iloc[0]

            # Top-level dimension scores
            metric_cols = st.columns(4)
            metric_cols[0].metric("D1: Sector Fit", f"{row['Sector Fit']:.1f}" if pd.notna(row["Sector Fit"]) else "—")
            metric_cols[1].metric("D2: Relationship", f"{row['Relationship Depth']:.1f}" if pd.notna(row["Relationship Depth"]) else "—")
            metric_cols[2].metric("D3: Halo Value", f"{row['Halo Value']:.1f}" if pd.notna(row["Halo Value"]) else "—")
            metric_cols[3].metric("D4: Emerging Mgr", f"{row['Emerging Mgr Fit']:.1f}" if pd.notna(row["Emerging Mgr Fit"]) else "—")

            # Sub-component breakdowns
            tab_d1, tab_d3, tab_d4 = st.tabs([
                "D1: Sector & Mandate Fit",
                "D3: Halo & Strategic Value",
                "D4: Emerging Manager Fit",
            ])

            with tab_d1:
                conf = row.get("D1 Confidence", "")
                if conf:
                    st.caption(f"Confidence: **{conf}**")
                if row.get("Sector Reasoning"):
                    st.info(row["Sector Reasoning"])
                _score_bar("LP Status", row.get("D1a LP Status"), "40%", row.get("D1a Reasoning", ""))
                _score_bar("Credit Allocation", row.get("D1b Credit"), "30%", row.get("D1b Reasoning", ""))
                _score_bar("Sustainability Mandate", row.get("D1c Sustainability"), "30%", row.get("D1c Reasoning", ""))

            with tab_d3:
                conf = row.get("D3 Confidence", "")
                if conf:
                    st.caption(f"Confidence: **{conf}**")
                if row.get("Halo Reasoning"):
                    st.info(row["Halo Reasoning"])
                _score_bar("Brand Recognition", row.get("D3a Brand"), "50%", row.get("D3a Reasoning", ""))
                _score_bar("Network Centrality", row.get("D3b Network"), "30%", row.get("D3b Reasoning", ""))
                _score_bar("Signal Specificity", row.get("D3c Specificity"), "20%", row.get("D3c Reasoning", ""))

            with tab_d4:
                conf = row.get("D4 Confidence", "")
                if conf:
                    st.caption(f"Confidence: **{conf}**")
                if row.get("Emerging Reasoning"):
                    st.info(row["Emerging Reasoning"])
                _score_bar("Structural Program", row.get("D4a Structural"), "40%", row.get("D4a Reasoning", ""))
                _score_bar("Behavioral Track Record", row.get("D4b Track Record"), "40%", row.get("D4b Reasoning", ""))
                _score_bar("Check Size Fit", row.get("D4c Check Size"), "20%", row.get("D4c Reasoning", ""))

                red_flags = row.get("D4 Red Flags", "")
                if red_flags and red_flags != "[]":
                    st.warning(f"Red flags: {red_flags}")

            # Multi-contact orgs
            if len(org_rows) > 1:
                st.markdown("**All contacts at this organization:**")
                st.dataframe(
                    org_rows[["Contact", "Role", "Email", "Contact Status", "Relationship Depth", "Composite Score", "Tier"]],
                    use_container_width=True,
                )

            # Check size
            check_low = row.get("Check Size Low ($M)")
            check_high = row.get("Check Size High ($M)")
            if pd.notna(check_low) and pd.notna(check_high):
                aum = row.get("AUM ($M)", 0)
                st.info(f"Estimated check size: **${check_low:.1f}M – ${check_high:.1f}M** (based on AUM of ${aum:.0f}M)")

    # --- Export ---
    st.divider()
    csv_export = filtered[display_cols].sort_values("Composite Score", ascending=False).to_csv(index=False)
    st.download_button(
        "Download scored pipeline as CSV",
        data=csv_export,
        file_name="pese_scored_pipeline.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
