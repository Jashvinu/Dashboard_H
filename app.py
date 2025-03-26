import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os
from process_data import preprocess_sales_data, load_processed_service_data
from s3_utils import read_csv_from_s3, check_file_exists_in_s3

# S3 configuration
S3_BUCKET = st.secrets["S3_BUCKET"]
S3_PREFIX = st.secrets["S3_PREFIX"]

# Set page configuration
st.set_page_config(
    page_title="Salon Business Dashboard",
    page_icon="💇",
    layout="wide"
)

# Title and description
st.title("Executive Business Dashboard")
st.markdown("### Sales and Service Performance Analytics")

# Load data


@st.cache_data
def load_data():
    # Check if processed data exists in S3, if not process the raw data
    if check_file_exists_in_s3(S3_BUCKET, f"{S3_PREFIX}processed_sales_data.csv"):
        sales_data = read_csv_from_s3(
            S3_BUCKET, f"{S3_PREFIX}processed_sales_data.csv")
    else:
        sales_data = preprocess_sales_data()

    # Load processed service data
    service_data = load_processed_service_data()

    return sales_data, service_data


# Display data processing status
with st.spinner("Loading data..."):
    sales_data, service_data = load_data()

# Check if service data was successfully loaded
has_service_data = not service_data.empty

# Main dashboard tabs
tab1, tab2, tab3, tab4 = st.tabs(
    ["MTD Sales Overview", "Outlet Comparison", "Service & Product Analysis", "Growth Analysis"])

with tab1:
    st.header("Monthly Sales Overview")

    # Filter controls
    col1, col2, col3 = st.columns(3)

    with col1:
        years = sorted(sales_data['Year'].unique())
        selected_year = st.selectbox("Select Year", years)

    with col2:
        brands = sorted(sales_data['BRAND'].unique())
        selected_brand = st.selectbox("Select Brand", ["All"] + list(brands))

    with col3:
        months = sorted(sales_data['Month'].unique())
        selected_month = st.selectbox("Select Month", ["All"] + list(months))

    # Filter data based on selections
    filtered_data = sales_data.copy()

    if selected_year != "All":
        filtered_data = filtered_data[filtered_data['Year'] == selected_year]

    if selected_brand != "All":
        filtered_data = filtered_data[filtered_data['BRAND'] == selected_brand]

    if selected_month != "All":
        filtered_data = filtered_data[filtered_data['Month'] == selected_month]

    # Display key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_sales = filtered_data['MTD SALES'].sum()
        st.metric("Total Sales", f"₹{total_sales:,.0f}")

    with col2:
        total_bills = filtered_data['MTD BILLS'].sum()
        st.metric("Total Bills", f"{total_bills:,.0f}")

    with col3:
        avg_bill_value = total_sales / total_bills if total_bills > 0 else 0
        st.metric("Average Bill Value", f"₹{avg_bill_value:,.0f}")

    with col4:
        total_outlets = filtered_data['SALON NAMES'].nunique()
        st.metric("Total Outlets", f"{total_outlets}")

    # MTD Sales by Outlet
    st.subheader("Sales by Outlet")

    # Group by salon names and calculate totals
    salon_sales = filtered_data.groupby(
        'SALON NAMES')['MTD SALES'].sum().reset_index()
    salon_sales = salon_sales.sort_values('MTD SALES', ascending=False)

    fig = px.bar(
        salon_sales,
        x='SALON NAMES',
        y='MTD SALES',
        title="MTD Sales by Outlet",
        labels={'MTD SALES': 'Sales (₹)', 'SALON NAMES': 'Outlet'},
        color='MTD SALES',
        color_continuous_scale='Viridis'
    )
    fig.update_layout(xaxis={'categoryorder': 'total descending'})
    st.plotly_chart(fig, use_container_width=True)

    # Sales Trend Over Months (if multiple months are available)
    if selected_month == "All":
        st.subheader("Monthly Sales Trend")

        monthly_sales = filtered_data.groupby(['Month', 'Year'])[
            'MTD SALES'].sum().reset_index()

        # Create a custom sort order for months
        month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                       'July', 'August', 'September', 'October', 'November', 'December']
        monthly_sales['Month_Sorted'] = pd.Categorical(
            monthly_sales['Month'], categories=month_order, ordered=True)
        monthly_sales = monthly_sales.sort_values('Month_Sorted')

        fig = px.line(
            monthly_sales,
            x='Month',
            y='MTD SALES',
            color='Year',
            title="Monthly Sales Trend",
            labels={'MTD SALES': 'Sales (₹)', 'Month': 'Month'},
            markers=True
        )
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("Outlet Comparison")

    # Select specific outlet to compare
    outlet_list = sorted(sales_data['SALON NAMES'].unique())
    selected_outlet = st.selectbox(
        "Select Outlet for Detailed Analysis", outlet_list)

    # Filter data for the selected outlet
    outlet_data = sales_data[sales_data['SALON NAMES'] == selected_outlet]

    # Group data by year and month
    outlet_yearly = outlet_data.groupby(['Year', 'Month'])[
        'MTD SALES'].sum().reset_index()

    # Create a custom sort order for months
    month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
    outlet_yearly['Month_Sorted'] = pd.Categorical(
        outlet_yearly['Month'], categories=month_order, ordered=True)
    outlet_yearly = outlet_yearly.sort_values(['Year', 'Month_Sorted'])

    # Display yearly comparison chart
    st.subheader(f"{selected_outlet} - Yearly Comparison")

    fig = px.bar(
        outlet_yearly,
        x='Month',
        y='MTD SALES',
        color='Year',
        barmode='group',
        title=f"Monthly Sales for {selected_outlet} by Year",
        labels={'MTD SALES': 'Sales (₹)', 'Month': 'Month', 'Year': 'Year'}
    )
    st.plotly_chart(fig, use_container_width=True)

    # Calculate year-over-year growth
    if len(outlet_yearly['Year'].unique()) > 1:
        st.subheader("Year-over-Year Growth")

        try:
            # Pivot data for easier comparison
            pivot_data = outlet_yearly.pivot_table(
                index='Month_Sorted',
                columns='Year',
                values='MTD SALES'
            ).reset_index()

            # Get years from the pivot table columns
            years = [col for col in pivot_data.columns if col != 'Month_Sorted']

            if len(years) > 1:
                # Calculate YoY growth percentages
                for i in range(1, len(years)):
                    current_year = years[i]
                    prev_year = years[i-1]
                    colname = f"Growth {prev_year} to {current_year}"
                    pivot_data[colname] = (
                        (pivot_data[current_year] / pivot_data[prev_year]) - 1) * 100

                # Display the growth table
                pivot_data = pivot_data.rename(
                    columns={'Month_Sorted': 'Month'})
                pivot_data['Month'] = pivot_data['Month'].astype(str)

                # Only show growth columns
                growth_cols = [
                    col for col in pivot_data.columns if 'Growth' in str(col)]

                if growth_cols and not pivot_data.empty:
                    # Create the growth visualization
                    fig = go.Figure()

                    for col in growth_cols:
                        fig.add_trace(go.Bar(
                            x=pivot_data['Month'],
                            y=pivot_data[col],
                            name=col
                        ))

                    fig.update_layout(
                        title=f"Monthly Sales Growth (%) for {selected_outlet}",
                        yaxis_title="Growth (%)",
                        xaxis_title="Month"
                    )

                    st.plotly_chart(fig, use_container_width=True)

                    # Show the actual data table
                    display_cols = ['Month'] + years + growth_cols
                    st.dataframe(pivot_data[display_cols],
                                 use_container_width=True)
                else:
                    st.info(
                        f"Not enough data to compare growth for {selected_outlet} across years.")
            else:
                st.info(
                    f"Only one year of data available for {selected_outlet}. Need at least two years to calculate growth.")
        except Exception as e:
            st.error(f"Could not calculate growth data: {e}")
            st.info(
                f"Please ensure {selected_outlet} has data for multiple years and months.")

    # Daily Sales Analysis
    if 'DAY SALES' in sales_data.columns:
        st.subheader("Daily Sales Analysis")

        # Display day-wise sales if available
        outlet_daily = sales_data[
            (sales_data['SALON NAMES'] == selected_outlet) &
            # Changed from notna to ~pd.isna for clarity
            (~pd.isna(sales_data['DAY SALES'])) &
            # Additional check for empty strings
            (sales_data['DAY SALES'] != '') &
            # Additional check for zero values
            (sales_data['DAY SALES'] != 0)
        ]

        if not outlet_daily.empty:
            # Group by day and calculate averages
            try:
                daily_avg = outlet_daily.groupby(['Year', 'Month', 'DAY SALES'])[
                    'MTD SALES'].mean().reset_index()

                fig = px.line(
                    daily_avg,
                    x='DAY SALES',
                    y='MTD SALES',
                    color='Year',
                    line_group='Month',
                    title=f"Daily Sales for {selected_outlet}",
                    labels={'MTD SALES': 'Sales (₹)', 'DAY SALES': 'Day'}
                )
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Error processing daily sales data: {e}")
                st.info(
                    "Daily sales data format may be incorrect. Check the 'DAY SALES' column.")
        else:
            st.info(
                f"No daily sales data available for {selected_outlet}. The 'DAY SALES' column is empty or not properly formatted.")

with tab3:
    st.header("Service & Product Analysis")

    # Add Hair, Skin, Spa and Products breakdown
    st.subheader("Hair, Skin, Spa and Products Breakdown")

    try:
        # Load category data if available in S3
        category_file_key = f"{S3_PREFIX}outputs/Hair___skin__spa_and_products___For_each_20250326_222907.csv"
        if check_file_exists_in_s3(S3_BUCKET, category_file_key):
            category_data = read_csv_from_s3(S3_BUCKET, category_file_key)

            # Group by Business Unit
            business_unit_sales = category_data.groupby(
                'Business Unit')['Total_Sales'].sum().reset_index()

            # Create pie chart for business units
            fig_bu = px.pie(
                business_unit_sales,
                values='Total_Sales',
                names='Business Unit',
                title="Sales by Business Unit",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Bold
            )

            # Group by Item Category and Business Unit
            # Select top 15 categories by sales
            top_categories = category_data.sort_values(
                'Total_Sales', ascending=False).head(15)

            # Create bar chart for top 15 categories
            fig_cat = px.bar(
                top_categories,
                x='Item Category',
                y='Total_Sales',
                color='Business Unit',
                title="Top 15 Service/Product Categories",
                labels={
                    'Total_Sales': 'Sales (₹)', 'Item Category': 'Category'},
                text_auto='.2s'  # Format text with automatic formatting
            )
            fig_cat.update_layout(xaxis={'categoryorder': 'total descending'})

            # Display charts in columns
            col1, col2 = st.columns(2)

            with col1:
                st.plotly_chart(fig_bu, use_container_width=True)

            with col2:
                # Create treemap for business unit and category breakdown
                fig_tree = px.treemap(
                    category_data,
                    path=['Business Unit', 'Item Category'],
                    values='Total_Sales',
                    color='Total_Sales',
                    color_continuous_scale='Viridis',
                    title="Hierarchical View of Sales"
                )
                st.plotly_chart(fig_tree, use_container_width=True)

            # Display bar chart for top categories
            st.plotly_chart(fig_cat, use_container_width=True)

            # Add table with top categories by business unit
            st.subheader("Top Categories by Business Unit")

            # Create pivot table
            pivot = pd.pivot_table(
                category_data,
                values=['Total_Sales', 'Total_Quantity'],
                index='Item Category',
                columns='Business Unit',
                aggfunc='sum',
                fill_value=0
            )

            # Format for display - flatten columns and format values
            pivot_flat = pivot.reset_index()
            formatted_pivot = pivot_flat.copy()

            # Format the sales columns with ₹ symbol
            for col in formatted_pivot.columns:
                if isinstance(col, tuple) and col[0] == 'Total_Sales':
                    formatted_pivot[col] = formatted_pivot[col].apply(
                        lambda x: f"₹{x:,.0f}" if x > 0 else "")

            st.dataframe(formatted_pivot, use_container_width=True)

        else:
            st.info(
                "Category breakdown data not available. Please upload the category data file to the S3 bucket.")
    except Exception as e:
        st.error(f"Error processing category data: {e}")
        st.info("Make sure the category data file is correctly formatted.")

    if has_service_data:
        # Advanced filtering options
        st.subheader("Filter Service Data")

        with st.expander("Advanced Filters", expanded=False):
            filter_cols = st.columns(3)

            with filter_cols[0]:
                service_years = sorted(service_data['Year'].unique())
                selected_service_year = st.selectbox(
                    "Select Year", service_years)

                center_names = sorted(service_data['Center Name'].unique())
                selected_center = st.selectbox(
                    "Select Center", ["All"] + list(center_names))

            with filter_cols[1]:
                item_categories = ["All"] + \
                    sorted(service_data['Service_Type'].unique())
                selected_item_category = st.selectbox(
                    "Select Service Type", item_categories)

                if 'Item Category' in service_data.columns:
                    subcategories = [
                        "All"] + sorted(service_data['Item Category'].dropna().unique())
                    selected_subcategory = st.selectbox(
                        "Select Item Category", subcategories)
                else:
                    selected_subcategory = "All"

            with filter_cols[2]:
                if 'Business Unit' in service_data.columns:
                    business_units = [
                        "All"] + sorted(service_data['Business Unit'].dropna().unique())
                    selected_business_unit = st.selectbox(
                        "Select Business Unit", business_units)
                else:
                    selected_business_unit = "All"

                if 'Item Subcategory' in service_data.columns:
                    item_subcategories = [
                        "All"] + sorted(service_data['Item Subcategory'].dropna().unique())
                    selected_item_subcategory = st.selectbox(
                        "Select Item Subcategory", item_subcategories)
                else:
                    selected_item_subcategory = "All"

        # Filter service data
        filtered_service_data = service_data.copy()
        filtered_service_data = filtered_service_data[filtered_service_data['Year']
                                                      == selected_service_year]

        if selected_center != "All":
            filtered_service_data = filtered_service_data[
                filtered_service_data['Center Name'] == selected_center]

        if selected_item_category != "All":
            filtered_service_data = filtered_service_data[filtered_service_data['Service_Type']
                                                          == selected_item_category]

        if selected_subcategory != "All" and 'Item Category' in filtered_service_data.columns:
            filtered_service_data = filtered_service_data[
                filtered_service_data['Item Category'] == selected_subcategory]

        if selected_business_unit != "All" and 'Business Unit' in filtered_service_data.columns:
            filtered_service_data = filtered_service_data[
                filtered_service_data['Business Unit'] == selected_business_unit]

        if selected_item_subcategory != "All" and 'Item Subcategory' in filtered_service_data.columns:
            filtered_service_data = filtered_service_data[
                filtered_service_data['Item Subcategory'] == selected_item_subcategory]

        # Service Categories Analysis
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Service Categories Breakdown")

            # Calculate metrics by service category
            category_sales = filtered_service_data.groupby(
                'Service_Type')['Total_Sales'].sum().reset_index()

            # Create service category visualization
            fig = px.pie(
                category_sales,
                values='Total_Sales',
                names='Service_Type',
                title="Sales Distribution by Category",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.G10
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Service vs Product Sales")

            service_product = filtered_service_data.groupby(
                'Category')['Total_Sales'].sum().reset_index()

            fig = px.pie(
                service_product,
                values='Total_Sales',
                names='Category',
                title="Service vs Product Sales Distribution",
                color_discrete_sequence=['#3366CC', '#FF9900']
            )
            st.plotly_chart(fig, use_container_width=True)

        # Display detailed service category metrics
        st.subheader("Service Category Metrics")

        category_details = filtered_service_data.groupby('Service_Type').agg({
            'Total_Sales': 'sum',
            'Transaction_Count': 'sum'
        }).reset_index()

        category_details['Average_Transaction'] = category_details['Total_Sales'] / \
            category_details['Transaction_Count']

        # Format for display
        category_details['Total_Sales'] = category_details['Total_Sales'].apply(
            lambda x: f"₹{x:,.0f}")
        category_details['Average_Transaction'] = category_details['Average_Transaction'].apply(
            lambda x: f"₹{x:,.0f}")

        # Rename columns for display
        category_details.columns = [
            'Service Category', 'Total Sales', 'Transaction Count', 'Average Transaction']

        st.dataframe(category_details, use_container_width=True)

        # Center-wise Analysis (NEW)
        st.subheader("Center-wise Service Analysis")

        # Group by center and calculate totals
        center_sales = filtered_service_data.groupby('Center Name').agg({
            'Total_Sales': 'sum',
            'Transaction_Count': 'sum'
        }).reset_index()

        center_sales['Average_Transaction'] = center_sales['Total_Sales'] / \
            center_sales['Transaction_Count']
        center_sales = center_sales.sort_values('Total_Sales', ascending=False)

        # Create center sales bar chart
        fig = px.bar(
            center_sales,
            x='Center Name',
            y='Total_Sales',
            title="Total Sales by Center",
            color='Total_Sales',
            labels={'Total_Sales': 'Sales (₹)', 'Center Name': 'Center'},
            text='Total_Sales'
        )
        fig.update_traces(texttemplate='₹%{text:,.0f}', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

        # Compare centers across years if multiple years available
        if len(service_years) > 1:
            st.subheader("Center Performance Across Years")

            # Group by center and year
            yearly_center_sales = service_data.groupby(['Center Name', 'Year'])[
                'Total_Sales'].sum().reset_index()

            # Create a comparison visualization
            fig = px.bar(
                yearly_center_sales,
                x='Center Name',
                y='Total_Sales',
                color='Year',
                barmode='group',
                title="Center Sales by Year",
                labels={
                    'Total_Sales': 'Sales (₹)', 'Center Name': 'Center', 'Year': 'Year'}
            )
            st.plotly_chart(fig, use_container_width=True)

            # Calculate year-over-year growth for centers
            st.subheader("Center Growth Analysis")

            # Create a pivot table for easier comparison
            center_pivot = yearly_center_sales.pivot_table(
                index='Center Name',
                columns='Year',
                values='Total_Sales'
            ).reset_index()

            # Calculate growth percentages between years
            years = sorted(service_data['Year'].unique())
            growth_data = []

            for center in center_pivot['Center Name']:
                center_row = {'Center Name': center}

                for i in range(1, len(years)):
                    current_year = years[i]
                    prev_year = years[i-1]

                    # Get sales values
                    prev_sales = center_pivot.loc[center_pivot['Center Name']
                                                  == center, prev_year].values[0]
                    current_sales = center_pivot.loc[center_pivot['Center Name']
                                                     == center, current_year].values[0]

                    # Calculate growth
                    if prev_sales > 0:
                        growth_pct = ((current_sales / prev_sales) - 1) * 100
                    else:
                        growth_pct = float('inf')

                    # Add to row
                    center_row[f'Growth {prev_year} to {current_year}'] = growth_pct

                growth_data.append(center_row)

            growth_df = pd.DataFrame(growth_data)

            # Sort by the most recent growth
            if len(years) > 1:
                latest_growth_col = f'Growth {years[-2]} to {years[-1]}'
                growth_df = growth_df.sort_values(
                    latest_growth_col, ascending=False)

            # Create growth chart
            growth_cols = [col for col in growth_df.columns if 'Growth' in col]

            if growth_cols:
                melted_growth = pd.melt(
                    growth_df,
                    id_vars=['Center Name'],
                    value_vars=growth_cols,
                    var_name='Period',
                    value_name='Growth (%)'
                )

                fig = px.bar(
                    melted_growth,
                    x='Center Name',
                    y='Growth (%)',
                    color='Period',
                    barmode='group',
                    title="Year-over-Year Growth by Center (%)",
                    labels={'Growth (%)': 'Growth %', 'Center Name': 'Center'},
                    text='Growth (%)'
                )
                fig.update_traces(
                    texttemplate='%{text:.1f}%', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)

                # Format growth data for display
                display_growth = growth_df.copy()
                for col in growth_cols:
                    display_growth[col] = display_growth[col].apply(
                        lambda x: f"{x:.2f}%" if not pd.isna(x) and not np.isinf(x) else "N/A")

                st.dataframe(display_growth, use_container_width=True)
    else:
        st.warning(
            "Service data is not available or was too large to process. Using only sales data for this analysis.")

        # Display brand-based analysis instead
        brand_sales = sales_data.groupby(['BRAND', 'Year'])[
            'MTD SALES'].sum().reset_index()

        fig = px.bar(
            brand_sales,
            x='BRAND',
            y='MTD SALES',
            color='Year',
            barmode='group',
            title="Sales by Brand and Year",
            labels={'MTD SALES': 'Sales (₹)', 'BRAND': 'Brand'}
        )
        st.plotly_chart(fig, use_container_width=True)

        # Add comparison of salon names
        st.subheader("Salon Names Comparison Across Years")

        salon_yearly_sales = sales_data.groupby(['SALON NAMES', 'Year'])[
            'MTD SALES'].sum().reset_index()

        fig = px.bar(
            salon_yearly_sales,
            x='SALON NAMES',
            y='MTD SALES',
            color='Year',
            barmode='group',
            title="Salon Sales by Year",
            labels={'MTD SALES': 'Sales (₹)', 'SALON NAMES': 'Salon'}
        )
        fig.update_layout(xaxis={'categoryorder': 'total descending'})
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.header("Growth Analysis")

    # Year selection
    years = sorted(sales_data['Year'].unique())

    # Display overall growth from first to last year if we have at least 2023 and 2025
    if '2023' in years and '2025' in years:
        st.subheader("Total Growth from 2023 to 2025")

        data_2023 = sales_data[sales_data['Year'] == '2023']
        data_2025 = sales_data[sales_data['Year'] == '2025']

        total_2023 = data_2023['MTD SALES'].sum()
        total_2025 = data_2025['MTD SALES'].sum()

        overall_growth = ((total_2025 / total_2023) - 1) * 100

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Sales (2023)", f"₹{total_2023:,.0f}")

        with col2:
            st.metric("Total Sales (2025)", f"₹{total_2025:,.0f}")

        with col3:
            st.metric("2-Year Growth", f"{overall_growth:.2f}%")

        # Calculate outlet-specific growth from 2023 to 2025
        salon_2023 = data_2023.groupby('SALON NAMES')[
            'MTD SALES'].sum().reset_index()
        salon_2025 = data_2025.groupby('SALON NAMES')[
            'MTD SALES'].sum().reset_index()

        salon_growth = pd.merge(
            salon_2023, salon_2025,
            on='SALON NAMES',
            suffixes=('_2023', '_2025')
        )

        salon_growth['Growth_Amount'] = salon_growth['MTD SALES_2025'] - \
            salon_growth['MTD SALES_2023']
        salon_growth['Growth_Percent'] = (
            (salon_growth['MTD SALES_2025'] / salon_growth['MTD SALES_2023']) - 1) * 100
        salon_growth = salon_growth.sort_values(
            'Growth_Percent', ascending=False)

        # Display the 2-year growth chart
        fig = px.bar(
            salon_growth,
            x='SALON NAMES',
            y='Growth_Percent',
            title="Total Growth by Outlet (2023 to 2025)",
            labels={'Growth_Percent': 'Growth (%)', 'SALON NAMES': 'Outlet'},
            color='Growth_Percent',
            color_continuous_scale='RdYlGn',
            text='Growth_Percent'
        )

        fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig.update_layout(xaxis={'categoryorder': 'total descending'})

        st.plotly_chart(fig, use_container_width=True)

    if len(years) >= 2:
        st.subheader("Year-to-Year Comparison")

        col1, col2 = st.columns(2)

        with col1:
            base_year = st.selectbox("Base Year", years[:-1], index=0)

        with col2:
            compare_year = st.selectbox(
                "Comparison Year", [y for y in years if y > base_year], index=0)

        # Filter data for selected years
        base_data = sales_data[sales_data['Year'] == base_year]
        compare_data = sales_data[sales_data['Year'] == compare_year]

        # Group by salon
        base_by_salon = base_data.groupby(
            'SALON NAMES')['MTD SALES'].sum().reset_index()
        compare_by_salon = compare_data.groupby(
            'SALON NAMES')['MTD SALES'].sum().reset_index()

        # Merge data
        growth_data = pd.merge(base_by_salon, compare_by_salon,
                               on='SALON NAMES', suffixes=('_base', '_compare'))

        # Calculate growth
        growth_data['Growth_Amount'] = growth_data['MTD SALES_compare'] - \
            growth_data['MTD SALES_base']
        growth_data['Growth_Percent'] = (
            (growth_data['MTD SALES_compare'] / growth_data['MTD SALES_base']) - 1) * 100

        # Sort by growth percentage
        growth_data = growth_data.sort_values(
            'Growth_Percent', ascending=False)

        # Display growth chart
        st.subheader(f"Growth Analysis: {base_year} to {compare_year}")

        fig = px.bar(
            growth_data,
            x='SALON NAMES',
            y='Growth_Percent',
            title=f"Growth Percentage by Outlet ({base_year} to {compare_year})",
            labels={'Growth_Percent': 'Growth (%)', 'SALON NAMES': 'Outlet'},
            color='Growth_Percent',
            color_continuous_scale='RdYlGn',
            text='Growth_Percent'
        )

        fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig.update_layout(xaxis={'categoryorder': 'total descending'})

        st.plotly_chart(fig, use_container_width=True)

        # Display growth table
        st.subheader("Detailed Growth Table")

        # Format the table
        display_growth = growth_data.copy()
        display_growth['MTD SALES_base'] = display_growth['MTD SALES_base'].apply(
            lambda x: f"₹{x:,.0f}")
        display_growth['MTD SALES_compare'] = display_growth['MTD SALES_compare'].apply(
            lambda x: f"₹{x:,.0f}")
        display_growth['Growth_Amount'] = display_growth['Growth_Amount'].apply(
            lambda x: f"₹{x:,.0f}")
        display_growth['Growth_Percent'] = display_growth['Growth_Percent'].apply(
            lambda x: f"{x:.2f}%")

        # Rename columns for display
        display_growth.columns = [
            'Outlet', f'Sales ({base_year})', f'Sales ({compare_year})', 'Growth (Amount)', 'Growth (%)']

        st.dataframe(display_growth, use_container_width=True)

        # Overall growth
        st.subheader("Overall Business Growth")

        total_base = base_data['MTD SALES'].sum()
        total_compare = compare_data['MTD SALES'].sum()
        overall_growth = ((total_compare / total_base) - 1) * 100

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(f"Total Sales ({base_year})", f"₹{total_base:,.0f}")

        with col2:
            st.metric(f"Total Sales ({compare_year})",
                      f"₹{total_compare:,.0f}")

        with col3:
            st.metric("Overall Growth",
                      f"{overall_growth:.2f}%", f"{overall_growth:.2f}%")

        # Month-by-month growth visualization
        st.subheader("Month-by-Month Growth")

        # Aggregate by month for both years
        base_monthly = base_data.groupby(
            'Month')['MTD SALES'].sum().reset_index()
        compare_monthly = compare_data.groupby(
            'Month')['MTD SALES'].sum().reset_index()

        # Merge the data
        monthly_growth = pd.merge(
            base_monthly, compare_monthly, on='Month', suffixes=('_base', '_compare'))
        monthly_growth['Growth_Percent'] = (
            (monthly_growth['MTD SALES_compare'] / monthly_growth['MTD SALES_base']) - 1) * 100

        # Create a custom sort order for months
        month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                       'July', 'August', 'September', 'October', 'November', 'December']
        monthly_growth['Month_Sorted'] = pd.Categorical(
            monthly_growth['Month'], categories=month_order, ordered=True)
        monthly_growth = monthly_growth.sort_values('Month_Sorted')

        # Create the visualization
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Add bar chart for growth percentage
        fig.add_trace(
            go.Bar(
                x=monthly_growth['Month'],
                y=monthly_growth['Growth_Percent'],
                name='Growth %',
                marker_color='lightgreen'
            ),
            secondary_y=False
        )

        # Add line charts for sales values
        fig.add_trace(
            go.Scatter(
                x=monthly_growth['Month'],
                y=monthly_growth['MTD SALES_base'],
                name=f'Sales {base_year}',
                mode='lines+markers',
                line=dict(color='blue')
            ),
            secondary_y=True
        )

        fig.add_trace(
            go.Scatter(
                x=monthly_growth['Month'],
                y=monthly_growth['MTD SALES_compare'],
                name=f'Sales {compare_year}',
                mode='lines+markers',
                line=dict(color='red')
            ),
            secondary_y=True
        )

        fig.update_layout(
            title=f"Monthly Sales Comparison: {base_year} vs {compare_year}",
            hovermode="x unified"
        )

        fig.update_yaxes(title_text="Growth (%)", secondary_y=False)
        fig.update_yaxes(title_text="Sales (₹)", secondary_y=True)

        st.plotly_chart(fig, use_container_width=True)

        # Brand comparison
        st.subheader("Brand Performance Comparison")

        # Group by brand
        brand_base = base_data.groupby(
            'BRAND')['MTD SALES'].sum().reset_index()
        brand_compare = compare_data.groupby(
            'BRAND')['MTD SALES'].sum().reset_index()

        # Merge brand data
        brand_growth = pd.merge(brand_base, brand_compare,
                                on='BRAND', suffixes=('_base', '_compare'))
        brand_growth['Growth_Percent'] = (
            (brand_growth['MTD SALES_compare'] / brand_growth['MTD SALES_base']) - 1) * 100

        # Create visualization
        fig = px.bar(
            brand_growth,
            x='BRAND',
            y=['MTD SALES_base', 'MTD SALES_compare'],
            title=f"Brand Performance: {base_year} vs {compare_year}",
            barmode='group',
            labels={
                'value': 'Sales (₹)',
                'BRAND': 'Brand',
                'variable': 'Year'
            }
        )

        # Add growth percentage as text
        for i, brand in enumerate(brand_growth['BRAND']):
            growth_pct = brand_growth.iloc[i]['Growth_Percent']
            fig.add_annotation(
                x=brand,
                y=max(brand_growth.iloc[i]['MTD SALES_base'],
                      brand_growth.iloc[i]['MTD SALES_compare']),
                text=f"{growth_pct:.1f}%",
                showarrow=True,
                arrowhead=1
            )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(
            "Multiple years of data are required for growth analysis. Current dataset has only one year.")

    # T Nagar Specific Analysis (as mentioned in requirements)
    st.header("T NAGAR Outlet Analysis")

    # Filter data for T NAGAR
    t_nagar_data = sales_data[sales_data['SALON NAMES'] == 'T NAGAR']

    if not t_nagar_data.empty:
        t_nagar_years = sorted(t_nagar_data['Year'].unique())

        # Display T NAGAR yearly comparison
        st.subheader("T NAGAR - Yearly Sales Comparison")

        fig = px.bar(
            t_nagar_data,
            x='Month',
            y='MTD SALES',
            color='Year',
            barmode='group',
            title="T NAGAR Monthly Sales by Year",
            labels={'MTD SALES': 'Sales (₹)', 'Month': 'Month', 'Year': 'Year'}
        )
        st.plotly_chart(fig, use_container_width=True)

        # Display growth metrics if multiple years
        if len(t_nagar_years) > 1:
            # Calculate year-over-year growth
            t_nagar_yearly = t_nagar_data.groupby(
                'Year')['MTD SALES'].sum().reset_index()

            # Calculate growth percentages
            t_nagar_growth = []
            for i in range(1, len(t_nagar_yearly)):
                current_year = t_nagar_yearly.iloc[i]['Year']
                prev_year = t_nagar_yearly.iloc[i-1]['Year']
                current_sales = t_nagar_yearly.iloc[i]['MTD SALES']
                prev_sales = t_nagar_yearly.iloc[i-1]['MTD SALES']
                growth_pct = ((current_sales / prev_sales) - 1) * 100
                t_nagar_growth.append({
                    'Year Comparison': f"{prev_year} to {current_year}",
                    'Growth (%)': f"{growth_pct:.2f}%"
                })

            # Display growth table
            st.dataframe(pd.DataFrame(t_nagar_growth),
                         use_container_width=True)

            # If we have 2023 and 2025, calculate total growth
            if '2023' in t_nagar_years and '2025' in t_nagar_years:
                sales_2023 = t_nagar_yearly[t_nagar_yearly['Year']
                                            == '2023']['MTD SALES'].values[0]
                sales_2025 = t_nagar_yearly[t_nagar_yearly['Year']
                                            == '2025']['MTD SALES'].values[0]
                total_growth = ((sales_2025 / sales_2023) - 1) * 100

                st.metric("Total Growth (2023 to 2025)",
                          f"{total_growth:.2f}%")
    else:
        st.info("No data available for T NAGAR outlet.")

# Add footer
st.markdown("---")
st.caption("Executive Dashboard - Created with Streamlit and Plotly")
