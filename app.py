import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os
from process_data import preprocess_sales_data, load_processed_service_data
from s3_utils import read_csv_from_s3, check_file_exists_in_s3


def format_indian_money(amount, format_type='full'):
    """
    Format money in Indian style with proper comma placement
    """
    if pd.isna(amount) or amount == 0:
        return "₹0"

    def format_with_indian_commas(num):
        """Helper function to add commas in Indian number system"""
        s = str(int(round(num)))
        if len(s) > 3:
            last3 = s[-3:]
            rest = s[:-3]
            formatted_rest = ''
            for i in range(len(rest)-1, -1, -2):
                if i == 0:
                    formatted_rest = rest[i] + formatted_rest
                else:
                    formatted_rest = ',' + \
                        rest[max(i-1, 0):i+1] + formatted_rest
            result = formatted_rest + ',' + last3 if formatted_rest else last3
            # Remove the leftmost comma if it exists
            if result.startswith(','):
                result = result[1:]
            return result
        return s

    # Format with Indian style commas
    formatted_amount = format_with_indian_commas(amount)
    return f"₹{formatted_amount}"


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
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["MTD Sales Overview", "Outlet Comparison", "Service & Product Analysis", "Growth Analysis", "MTD Analysis (2022-2025)"])

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
        st.metric("Total Sales", format_indian_money(total_sales))

    with col2:
        total_bills = filtered_data['MTD BILLS'].sum()
        st.metric("Total Bills", format_indian_money(total_bills))

    with col3:
        avg_bill_value = total_sales / total_bills if total_bills > 0 else 0
        st.metric("Average Bill Value", format_indian_money(avg_bill_value))

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
        labels={'MTD SALES': 'Sales', 'SALON NAMES': 'Outlet'},
        color='MTD SALES',
        color_continuous_scale='Viridis'
    )

    fig.update_traces(
        text=salon_sales['MTD SALES'].apply(format_indian_money),
        textposition='outside',
        hovertemplate='%{text}<extra></extra>'
    )
    fig.update_layout(
        xaxis={'categoryorder': 'total descending'},
        yaxis_title='Sales'
    )
    st.plotly_chart(fig, use_container_width=True)

    # Sales Trend Over Months
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
            labels={'MTD SALES': 'Sales', 'Month': 'Month'},
            markers=True
        )
        fig.update_traces(
            hovertemplate='%{text}<extra></extra>',
            text=monthly_sales['MTD SALES'].apply(format_indian_money)
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

    # Create a mapping dictionary for month names
    month_mapping = {
        'Jan': 'January',
        'Feb': 'February',
        'Mar': 'March',
        'Apr': 'April',
        'May': 'May',
        'Jun': 'June',
        'Jul': 'July',
        'Aug': 'August',
        'Sep': 'September',
        'Oct': 'October',
        'Nov': 'November',
        'Dec': 'December'
    }

    # Replace abbreviated month names with full names
    outlet_yearly['Month'] = outlet_yearly['Month'].replace(month_mapping)

    # Create the Month_Sorted column and sort
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
        barmode='stack',
        title=f"Monthly Sales for {selected_outlet} by Year",
        labels={'MTD SALES': 'Sales', 'Month': 'Month', 'Year': 'Year'}
    )
    fig.update_traces(
        hovertemplate='%{text}<extra></extra>',
        text=outlet_yearly['MTD SALES'].apply(format_indian_money)
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
                    # Format the growth percentage with % symbol
                    pivot_data[colname] = pivot_data[colname].apply(
                        lambda x: f"{x:.2f}%")

                # Display the growth table
                pivot_data = pivot_data.rename(
                    columns={'Month_Sorted': 'Month'})
                pivot_data['Month'] = pivot_data['Month'].astype(str)

                # Only show growth columns
                growth_cols = [
                    col for col in pivot_data.columns if 'Growth' in str(col)]

                if growth_cols and not pivot_data.empty:
                    # Get the latest year's data
                    latest_year = years[-1]

                    # Calculate projected values (110% of latest year)
                    pivot_data['Projected (10% Growth)'] = pivot_data[latest_year] * 1.10
                    # Format the projected values with currency symbol and Indian comma format
                    pivot_data['Projected (10% Growth)'] = pivot_data['Projected (10% Growth)'].apply(
                        lambda x: format_indian_money(x)
                    )

                    # Format the year columns with Indian comma format
                    for year in years:
                        pivot_data[year] = pivot_data[year].apply(
                            lambda x: format_indian_money(x))

                    # Update display columns to include projected growth
                    display_cols = ['Month'] + years + \
                        growth_cols + ['Projected (10% Growth)']

                    # Display using st.dataframe
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
                fig.update_traces(
                    hovertemplate='%{text}<extra></extra>',
                    text=daily_avg['MTD SALES'].apply(format_indian_money)
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

            # Check if Year column exists in category data
            if 'Year' in category_data.columns and len(category_data['Year'].unique()) > 1:
                # Add year filter with "Total" option
                year_options = ["Total"] + \
                    sorted(category_data['Year'].unique(), reverse=True)
                selected_breakdown_year = st.selectbox(
                    "Select Year for Category Breakdown", year_options)

                # Set breakdown_data for the charts
                if selected_breakdown_year == "Total":
                    breakdown_data = category_data.copy()
                    year_title = "All Years"
                else:
                    # Filter by year if applicable
                    breakdown_data = category_data[category_data['Year']
                                                   == selected_breakdown_year].copy()
                    year_title = selected_breakdown_year
            else:
                # No Year column or only one year, use all data
                breakdown_data = category_data.copy()
                year_title = "All Data"

            # Group by Business Unit
            business_unit_sales = breakdown_data.groupby(
                'Business Unit')['Total_Sales'].sum().reset_index()

            # Convert all values to Crores
            divisor = 10000000  # 1 crore = 10 million
            suffix = 'Cr'

            business_unit_sales['Display_Sales'] = business_unit_sales['Total_Sales'] / divisor

            # Create pie chart for business units
            fig_bu = px.pie(
                business_unit_sales,
                values='Total_Sales',
                names='Business Unit',
                title=f"Sales by Business Unit ({year_title})",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Bold
            )

            # Pre-format values for hover display
            business_unit_sales['formatted_sales'] = business_unit_sales['Total_Sales'].apply(
                lambda x: format_indian_money(x).replace('₹', '')
            )

            fig_bu.update_traces(
                text=business_unit_sales['formatted_sales'],
                texttemplate='₹%{text}',
                hovertemplate='₹%{text}<extra></extra>'
            )

            # Group by Item Category and Business Unit
            # Select top 15 categories by sales
            top_categories = breakdown_data.sort_values(
                'Total_Sales', ascending=False).head(15)

            top_categories['Display_Sales'] = top_categories['Total_Sales'] / divisor

            # Create bar chart for top 15 categories
            top_categories['formatted_sales'] = top_categories['Total_Sales'].apply(
                lambda x: format_indian_money(x).replace('₹', '')
            )

            fig_cat = px.bar(
                top_categories,
                x='Item Category',
                y='Total_Sales',
                color='Business Unit',
                title=f"Top 15 Service/Product Categories ({year_title})",
                labels={
                    'Total_Sales': 'Sales', 'Item Category': 'Category'},
            )
            fig_cat.update_traces(
                text=top_categories['formatted_sales'],
                texttemplate='₹%{text}',
                textposition='outside',
                hovertemplate='₹%{text}<extra></extra>'
            )
            fig_cat.update_layout(
                xaxis={'categoryorder': 'total descending'},
                yaxis_title='Sales'
            )

            # Display charts in columns
            col1, col2 = st.columns(2)

            with col1:
                st.plotly_chart(fig_bu, use_container_width=True)

            with col2:
                # Create treemap for business unit and category breakdown
                fig_tree = px.treemap(
                    breakdown_data,
                    path=['Business Unit', 'Item Category'],
                    values='Total_Sales',
                    color='Total_Sales',
                    color_continuous_scale='Viridis',
                    title=f"Hierarchical View of Sales ({year_title})"
                )

                # Format the labels to show both name and sales amount
                fig_tree.update_traces(
                    texttemplate='%{label}<br>₹%{value:,.0f}',
                    hovertemplate='%{label}<br>Total: %{value:,.0f}<extra></extra>'
                )

                # Update display for parent nodes
                for i in range(len(fig_tree.data[0].ids)):
                    if fig_tree.data[0].parents[i] == '':  # Root node
                        fig_tree.data[0].texttemplate = '%{label}<br>Total: ₹%{value:,.0f}'

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

            # Format the sales columns with ₹ symbol and Indian comma format
            for col in formatted_pivot.columns:
                if isinstance(col, tuple) and col[0] == 'Total_Sales':
                    formatted_pivot[col] = formatted_pivot[col].apply(
                        lambda x: format_indian_money(x) if x > 0 else ""
                    )

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
        st.subheader("Service Categories Breakdown")

        # Add year filter with "Total" option
        year_options = ["Total"] + \
            sorted(service_data['Year'].unique(), reverse=True)
        selected_breakdown_year = st.selectbox(
            "Select Year for Breakdown", year_options)

        # Filter data based on selected year or use all years
        if selected_breakdown_year == "Total":
            breakdown_data = service_data.copy()  # Use all data
            year_title = "All Years"
        else:
            breakdown_data = service_data[service_data['Year']
                                          == selected_breakdown_year].copy()
            year_title = selected_breakdown_year

        # Apply other filters except year
        if selected_center != "All":
            breakdown_data = breakdown_data[
                breakdown_data['Center Name'] == selected_center]

        if selected_item_category != "All":
            breakdown_data = breakdown_data[breakdown_data['Service_Type']
                                            == selected_item_category]

        if selected_subcategory != "All" and 'Item Category' in breakdown_data.columns:
            breakdown_data = breakdown_data[
                breakdown_data['Item Category'] == selected_subcategory]

        if selected_business_unit != "All" and 'Business Unit' in breakdown_data.columns:
            breakdown_data = breakdown_data[
                breakdown_data['Business Unit'] == selected_business_unit]

        if selected_item_subcategory != "All" and 'Item Subcategory' in breakdown_data.columns:
            breakdown_data = breakdown_data[
                breakdown_data['Item Subcategory'] == selected_item_subcategory]

        col1, col2 = st.columns(2)

        with col1:
            # Calculate metrics by service category
            category_sales = breakdown_data.groupby(
                'Service_Type')['Total_Sales'].sum().reset_index()

            # Create a mapping for more readable service names
            service_name_mapping = {
                'Hair': 'Hair Services',
                'Skin': 'Skin Care',
                'SPA': 'SPA & Massage',
                'Other Services': 'Other Services',
                'Product': 'Products'
            }

            # Apply the mapping
            category_sales['Display_Name'] = category_sales['Service_Type'].map(
                lambda x: service_name_mapping.get(x, x)
            )

            # Create service category visualization
            fig = px.pie(
                category_sales,
                values='Total_Sales',
                names='Display_Name',  # Use the display name
                title=f"Sales Distribution by Category ({year_title})",
                labels={'Total_Sales': 'Sales (in Lakhs)'},
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.G10
            )
            fig.update_traces(
                hovertemplate='₹%{y:,.0f}<extra></extra>'
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Service vs Product Sales")

            service_product = breakdown_data.groupby(
                'Category')['Total_Sales'].sum().reset_index()

            # Create a mapping for more readable category names
            category_name_mapping = {
                'Service': 'All Services',
                'Product': 'Products'
            }

            # Apply the mapping
            service_product['Display_Name'] = service_product['Category'].map(
                lambda x: category_name_mapping.get(x, x)
            )

            fig = px.pie(
                service_product,
                values='Total_Sales',
                names='Display_Name',
                title=f"Service vs Product Sales Distribution ({year_title})",
                color_discrete_sequence=['#3366CC', '#FF9900']
            )
            fig.update_traces(
                hovertemplate='₹%{y:,.0f}<extra></extra>'
            )
            st.plotly_chart(fig, use_container_width=True)

        # Display detailed service category metrics
        st.subheader(f"Service Category Metrics ({year_title})")

        category_details = breakdown_data.groupby('Service_Type').agg({
            'Total_Sales': 'sum',
            'Transaction_Count': 'sum'
        }).reset_index()

        category_details['Average_Transaction'] = category_details['Total_Sales'] / \
            category_details['Transaction_Count']

        # Apply the same mapping for display
        category_details['Service_Type'] = category_details['Service_Type'].map(
            lambda x: service_name_mapping.get(x, x)
        )

        # Format for display
        category_details['Total_Sales'] = category_details['Total_Sales'].apply(
            lambda x: format_indian_money(x, 'lakhs'))
        category_details['Average_Transaction'] = category_details['Average_Transaction'].apply(
            lambda x: format_indian_money(x, 'lakhs'))

        # Rename columns for display
        category_details.columns = [
            'Service Category', 'Total Sales', 'Transaction Count', 'Average Transaction']

        st.dataframe(category_details, use_container_width=True)

        # Center-wise Analysis
        st.subheader(f"Center-wise Service Analysis ({year_title})")

        # Group by center and calculate totals
        center_sales = breakdown_data.groupby('Center Name').agg({
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
            title=f"Total Sales by Center ({year_title})",
            color='Total_Sales',
            labels={
                'Total_Sales': 'Sales', 'Center Name': 'Center'},
            text='Total_Sales'
        )
        fig.update_traces(
            texttemplate='₹%{text:,.0f}',
            textposition='outside',
            hovertemplate='₹%{text:,.0f}<extra></extra>'
        )
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
                labels={'Total_Sales': 'Sales',
                        'Center Name': 'Center', 'Year': 'Year'}
            )
            fig.update_traces(
                hovertemplate='₹%{y:,.0f}<extra></extra>'
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
                    texttemplate='₹%{text:,.1f}%', textposition='outside'
                )
                fig.update_traces(
                    hovertemplate='₹%{y:,.0f}<extra></extra>'
                )
                st.plotly_chart(fig, use_container_width=True)

                # Format growth data for display
                display_growth = growth_df.copy()
                for col in growth_cols:
                    display_growth[col] = display_growth[col].apply(
                        lambda x: f"{x:.2f}%" if not pd.isna(x) and not np.isinf(x) else "N/A")

                # Format sales columns with Indian comma format
                for year in years:
                    display_growth[year] = display_growth[year].apply(
                        lambda x: format_indian_money(x))

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
        fig.update_traces(
            hovertemplate='₹%{y:,.0f}<extra></extra>'
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
        fig.update_traces(
            hovertemplate='₹%{y:,.0f}<extra></extra>'
        )
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
            st.metric("Total Sales (2023)",
                      format_indian_money(total_2023, 'lakhs'))

        with col2:
            st.metric("Total Sales (2025)",
                      format_indian_money(total_2025, 'lakhs'))

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
        fig.update_traces(
            texttemplate='%{text:.2f}%', textposition='outside'
        )
        fig.update_traces(
            hovertemplate='%{text}<extra></extra>'
        )
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
        fig.update_traces(
            texttemplate='%{text:.2f}%', textposition='outside'
        )
        fig.update_traces(
            hovertemplate='%{text}<extra></extra>'
        )
        st.plotly_chart(fig, use_container_width=True)

        # Display growth table
        st.subheader("Detailed Growth Table")

        # Format the table
        display_growth = growth_data.copy()
        display_growth['MTD SALES_base'] = display_growth['MTD SALES_base'].apply(
            lambda x: format_indian_money(x))
        display_growth['MTD SALES_compare'] = display_growth['MTD SALES_compare'].apply(
            lambda x: format_indian_money(x))
        display_growth['Growth_Amount'] = display_growth['Growth_Amount'].apply(
            lambda x: format_indian_money(x))
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
            st.metric(f"Total Sales ({base_year})",
                      format_indian_money(total_base, 'lakhs'))

        with col2:
            st.metric(f"Total Sales ({compare_year})",
                      format_indian_money(total_compare, 'lakhs'))

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

        fig.update_yaxes(
            title_text="Growth (%)",
            secondary_y=False
        )
        fig.update_yaxes(
            title_text="Sales (in Lakhs)",
            secondary_y=True
        )
        fig.update_traces(
            hovertemplate='%{text}<extra></extra>'
        )

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
        fig.update_traces(
            hovertemplate='%{text}<extra></extra>'
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
            barmode='stack',
            title="T NAGAR Monthly Sales by Year",
            labels={'MTD SALES': 'Sales (₹)', 'Month': 'Month', 'Year': 'Year'}
        )
        fig.update_traces(
            hovertemplate='%{text}<extra></extra>',
            text=t_nagar_data['MTD SALES'].apply(format_indian_money)
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

with tab5:
    st.header("MTD Analysis (2022-2025)")

    # Load all MTD files
    mtd_files = {
        "2022": "dataset/MTD - 2022.csv",
        "2023": "dataset/MTD - 2023.csv",
        "2024": "dataset/MTD - 2024.csv",
        "2025": "dataset/MTD - 2025.csv",
        "combined": "dataset/MTD - MTD 2022-2023-2024-2025.csv"
    }

    # Create a function to load MTD data
    def load_mtd_data(file_path):
        try:
            # Different loading logic based on file type
            if "2022-2023-2024-2025" in file_path:
                # Combined file has a different structure
                df = pd.read_csv(file_path, skiprows=1)
                df.columns = df.columns.str.strip()
                return df
            else:
                # Single year files
                df = pd.read_csv(file_path, skiprows=0)
                # Clean column names
                df.columns = [col.strip() for col in df.columns]
                # Remove empty rows and summary rows
                df = df[df['S.NO'].notna() & df['SALONS'].notna()]
                # Convert S.NO to numeric
                df['S.NO'] = pd.to_numeric(df['S.NO'], errors='coerce')
                return df
        except Exception as e:
            st.error(f"Error loading {file_path}: {e}")
            return pd.DataFrame()

    # Load combined MTD data
    if os.path.exists(mtd_files["combined"]):
        combined_mtd = load_mtd_data(mtd_files["combined"])

        # Show the monthly trend for all years
        st.subheader("Monthly Sales Trend (2022-2025)")

        # Reshape data for plotting
        if not combined_mtd.empty:
            # Melt the dataframe for easier plotting
            melted_data = pd.melt(
                combined_mtd,
                id_vars=['Month'],
                value_vars=['2022', '2023', '2024', '2025'],
                var_name='Year',
                value_name='Sales'
            )

            # Convert to numeric
            melted_data['Sales'] = pd.to_numeric(
                melted_data['Sales'], errors='coerce')

            # Add formatted sales for hover display
            melted_data['formatted_sales'] = melted_data['Sales'].apply(
                lambda x: format_indian_money(x).replace(
                    '₹', '') if pd.notna(x) else ''
            )

            # Create line chart
            fig = px.line(
                melted_data,
                x='Month',
                y='Sales',
                color='Year',
                markers=True,
                title="Monthly Sales Comparison Across Years",
                labels={'Sales': 'Sales', 'Month': 'Month'}
            )

            # Update traces to use formatted text
            fig.update_traces(
                text=melted_data['formatted_sales'],
                hovertemplate='₹%{text}<extra></extra>'
            )

            # Add percentage labels for year-over-year growth
            for year in ['2023', '2024', '2025']:
                if year in melted_data['Year'].unique():
                    # Get previous year
                    prev_year = str(int(year) - 1)

                    if prev_year in melted_data['Year'].unique():
                        # Calculate growth for each month
                        for month in combined_mtd['Month'].unique():
                            current = melted_data[(melted_data['Year'] == year) & (
                                melted_data['Month'] == month)]['Sales'].values
                            previous = melted_data[(melted_data['Year'] == prev_year) & (
                                melted_data['Month'] == month)]['Sales'].values

                            if len(current) > 0 and len(previous) > 0 and previous[0] > 0:
                                growth = ((current[0] / previous[0]) - 1) * 100

                                # Add annotation
                                fig.add_annotation(
                                    x=month,
                                    y=current[0],
                                    text=f"{growth:.1f}%",
                                    showarrow=True,
                                    arrowhead=1,
                                    xshift=5,
                                    yshift=10
                                )

            st.plotly_chart(fig, use_container_width=True)

            # Show the total for each year
            st.subheader("Yearly Totals")

            # Calculate yearly totals
            yearly_totals = {}
            for year in ['2022', '2023', '2024', '2025']:
                if year in combined_mtd.columns:
                    yearly_totals[year] = combined_mtd[year].sum()

            # Calculate year-over-year growth
            yearly_growth = []
            years = sorted(yearly_totals.keys())

            for i in range(1, len(years)):
                current_year = years[i]
                prev_year = years[i-1]

                growth_pct = (
                    (yearly_totals[current_year] / yearly_totals[prev_year]) - 1) * 100
                yearly_growth.append({
                    'Year': current_year,
                    'Sales': yearly_totals[current_year],
                    'Previous Year': prev_year,
                    'Previous Sales': yearly_totals[prev_year],
                    'Growth (%)': growth_pct
                })

            # Display in columns
            cols = st.columns(len(years))
            for i, year in enumerate(years):
                with cols[i]:
                    st.metric(
                        f"{year} Total",
                        format_indian_money(yearly_totals[year]),
                        f"{yearly_growth[i-1]['Growth (%)']:.2f}%" if i > 0 else None
                    )

            # Year-over-year growth chart
            if len(yearly_growth) > 0:
                st.subheader("Year-over-Year Growth")

                growth_df = pd.DataFrame(yearly_growth)

                fig = px.bar(
                    growth_df,
                    x='Year',
                    y='Growth (%)',
                    text='Growth (%)',
                    title="Year-over-Year Sales Growth",
                    labels={'Growth (%)': 'Growth (%)', 'Year': 'Year'}
                )
                fig.update_traces(
                    texttemplate='%{text:.2f}%', textposition='outside')

                st.plotly_chart(fig, use_container_width=True)

                # Show growth data table
                formatted_growth = growth_df.copy()
                formatted_growth['Sales'] = formatted_growth['Sales'].apply(
                    lambda x: format_indian_money(x))
                formatted_growth['Previous Sales'] = formatted_growth['Previous Sales'].apply(
                    lambda x: format_indian_money(x))
                formatted_growth['Growth (%)'] = formatted_growth['Growth (%)'].apply(
                    lambda x: f"{x:.2f}%")

                st.dataframe(formatted_growth, use_container_width=True)

    # Function to load MTD data specifically for salon analysis
    def load_mtd_salon_data(file_path, target_year):
        try:
            # Read the CSV file
            df = pd.read_csv(file_path)

            # Clean up column names
            df.columns = [str(col).strip() for col in df.columns]

            # Handle the empty first column if it exists
            if df.columns[0] == '' or df.columns[0] == 'Unnamed: 0':
                df = df.iloc[:, 1:]  # Skip the first empty column

            # Ensure we have a SALONS column
            if 'SALONS' not in df.columns:
                # Try to find it by similar names
                salon_col = None
                for col in df.columns:
                    if 'SALON' in str(col).upper():
                        salon_col = col
                        break

                if salon_col:
                    df = df.rename(columns={salon_col: 'SALONS'})
                else:
                    # MTD files typically have SALONS in the 3rd column
                    if len(df.columns) >= 3:
                        df = df.rename(columns={df.columns[2]: 'SALONS'})

            # Filter out rows where SALONS is missing or empty or contains summary data
            if 'SALONS' in df.columns:
                # Drop rows with NaN in SALONS
                df = df.dropna(subset=['SALONS'])

                # Drop rows where SALONS is empty or numeric (likely a total)
                df = df[df['SALONS'].astype(str).str.strip() != '']
                df = df[~df['SALONS'].astype(str).str.match(r'^\d+$')]

                # If S.NO exists, filter to only keep rows with valid S.NO
                if 'S.NO' in df.columns:
                    df = df[df['S.NO'].notna()]
                    # Convert S.NO to numeric to filter out summary rows
                    df['S.NO'] = pd.to_numeric(df['S.NO'], errors='coerce')
                    df = df[df['S.NO'].notna()]

            # Identify month columns
            month_columns = [col for col in df.columns if col in [
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December']]

            # Clean the data - select only SALONS and month columns
            salon_data = df[['SALONS'] + month_columns].copy()

            # Convert month columns to numeric, handling commas and currency symbols
            for month in month_columns:
                if salon_data[month].dtype == 'object':
                    salon_data[month] = salon_data[month].astype(
                        str).str.replace(',', '')
                    salon_data[month] = salon_data[month].astype(
                        str).str.replace('₹', '')
                    salon_data[month] = salon_data[month].astype(
                        str).str.replace(' ', '')
                salon_data[month] = pd.to_numeric(
                    salon_data[month], errors='coerce')

            # Remove any rows where SALONS contains "total" (case insensitive)
            salon_data = salon_data[~salon_data['SALONS'].astype(
                str).str.lower().str.contains('total')]

            return salon_data
        except Exception as e:
            return pd.DataFrame()

    # Load salon data directly from MTD files for comparison
    st.subheader("Salon Performance Analysis")

    # List all MTD files from the dataset directory
    mtd_files_all = {
        "2022": "dataset/MTD - 2022.csv",
        "2023": "dataset/MTD - 2023.csv",
        "2024": "dataset/MTD - 2024.csv",
        "2025": "dataset/MTD - 2025.csv"
    }

    # Get available files
    available_files = {}
    for year, path in mtd_files_all.items():
        if os.path.exists(path):
            available_files[year] = path

    if available_files:
        # Display available years and allow user to select
        available_years = list(available_files.keys())

        col1, col2 = st.columns(2)

        with col1:
            selected_years = st.multiselect(
                "Select Years", available_years, default=available_years)

        with col2:
            month_options = ["January", "February", "March", "April", "May", "June",
                             "July", "August", "September", "October", "November", "December"]
            selected_month = st.selectbox("Select Month", month_options)

        if selected_years and selected_month:
            st.write(f"### {selected_month} Salon Performance")

            # Load all selected years' data
            all_salon_data = {}

            for year in selected_years:
                file_path = available_files[year]
                salon_data = load_mtd_salon_data(file_path, year)

                if not salon_data.empty and selected_month in salon_data.columns:
                    # Prepare the data
                    data = salon_data[['SALONS', selected_month]].copy()
                    # Rename month column to year
                    data.columns = ['SALONS', year]
                    # Store in dictionary
                    all_salon_data[year] = data

            # If we have data from multiple years, merge and create visualizations
            if len(all_salon_data) > 0:
                # Merge data from all years
                merged_data = None

                for year, data in all_salon_data.items():
                    if merged_data is None:
                        merged_data = data
                    else:
                        merged_data = pd.merge(
                            merged_data, data, on='SALONS', how='outer')

                # Fill NaN values with 0
                for year in selected_years:
                    if year in merged_data.columns:
                        merged_data[year] = pd.to_numeric(
                            merged_data[year], errors='coerce').fillna(0)

                # Sort by the latest year's data
                if selected_years:
                    latest_year = max(selected_years)
                    if latest_year in merged_data.columns:
                        merged_data = merged_data.sort_values(
                            by=latest_year, ascending=False)

                # Top salons visualization
                top_salons = merged_data.head(15)

                # Add formatted sales for hover display
                for year in selected_years:
                    if year in top_salons.columns:
                        top_salons[f'formatted_{year}'] = top_salons[year].apply(
                            lambda x: format_indian_money(x).replace(
                                '₹', '') if pd.notna(x) and x > 0 else ''
                        )

                # Create the chart
                fig = px.bar(
                    top_salons,
                    x='SALONS',
                    y=selected_years,
                    barmode='group',
                    title=f"Top 15 Salons - {selected_month} Performance",
                    labels={
                        'value': 'Sales', 'SALONS': 'Salon', 'variable': 'Year'}
                )

                # Update traces to use formatted text
                for i, year in enumerate(selected_years):
                    if year in top_salons.columns:
                        fig.data[i].text = top_salons[f'formatted_{year}']
                        fig.data[i].texttemplate = '₹%{text}'
                        fig.data[i].hovertemplate = '₹%{text}<extra></extra>'

                # Add growth percentages for multiple years
                if len(selected_years) > 1:
                    for i in range(1, len(selected_years)):
                        current_year = selected_years[i]
                        prev_year = selected_years[i-1]

                        for j, salon in enumerate(top_salons['SALONS']):
                            salon_row = top_salons[top_salons['SALONS']
                                                   == salon].iloc[0]

                            prev_val = salon_row[prev_year]
                            curr_val = salon_row[current_year]

                            if prev_val > 0:
                                growth = ((curr_val / prev_val) - 1) * 100
                                # Add annotation for significant growth
                                if abs(growth) > 10:
                                    fig.add_annotation(
                                        x=salon,
                                        y=curr_val,
                                        text=f"{growth:.1f}%",
                                        showarrow=True,
                                        arrowhead=1,
                                        yshift=10
                                    )

                st.plotly_chart(fig, use_container_width=True)

                # Create data table with all salons
                st.subheader("Complete Salon Data")

                # Format for display
                display_data = merged_data.copy()

                # Format monetary values
                for year in selected_years:
                    if year in display_data.columns:
                        display_data[year] = display_data[year].apply(
                            lambda x: format_indian_money(x) if x > 0 else "")

                # Add growth columns
                if len(selected_years) > 1:
                    for i in range(1, len(selected_years)):
                        current_year = selected_years[i]
                        prev_year = selected_years[i-1]

                        growth_col = f"Growth {prev_year}-{current_year}"

                        # Calculate growth
                        merged_data[growth_col] = merged_data.apply(
                            lambda row: (
                                (row[current_year] / row[prev_year]) - 1) * 100
                            if row[prev_year] > 0 else 0,
                            axis=1
                        )

                        # Format growth column
                        display_data[growth_col] = merged_data[growth_col].apply(
                            lambda x: f"{x:.2f}%" if x != 0 else ""
                        )

                # Display the table
                st.dataframe(display_data, use_container_width=True)

                # Summary statistics
                st.subheader("Summary Statistics")

                # Calculate total sales per year
                totals = {}
                for year in selected_years:
                    if year in merged_data.columns:
                        totals[year] = merged_data[year].sum()

                # Calculate year-over-year growth
                growth_stats = []
                years = sorted(selected_years)

                for i in range(1, len(years)):
                    curr_year = years[i]
                    prev_year = years[i-1]

                    if curr_year in totals and prev_year in totals:
                        prev_total = totals[prev_year]
                        curr_total = totals[curr_year]

                        if prev_total > 0:
                            growth_pct = ((curr_total / prev_total) - 1) * 100
                            growth_stats.append({
                                'From': prev_year,
                                'To': curr_year,
                                'Growth (%)': growth_pct
                            })

                # Display in columns
                cols = st.columns(len(selected_years))

                for i, year in enumerate(sorted(selected_years)):
                    with cols[i]:
                        st.metric(
                            f"{year} Total",
                            format_indian_money(totals[year]),
                            f"{growth_stats[i-1]['Growth (%)']:.2f}%" if i > 0 else None
                        )
            else:
                st.warning(
                    f"No data available for {selected_month} in the selected years.")
        else:
            st.info("Please select at least one year and a month.")
    else:
        st.warning(
            "No MTD files found in the dataset directory. Please ensure files are named correctly (e.g., 'MTD - 2022.csv').")

# Direct file reading function


def read_salon_file(file_path):
    """
    Read salon data directly from file with different approaches to ensure compatibility
    """
    try:
        # Try multiple approaches to read the file

        # Approach 1: Standard read
        df = pd.read_csv(file_path)
        if df.shape[1] >= 10 and 'SALONS' in df.columns:
            return df

        # Approach 2: Skip first row
        df = pd.read_csv(file_path, skiprows=1)
        if df.shape[1] >= 10:
            # Identify the salon column
            salon_col = None
            for col in df.columns:
                if 'SALON' in col.upper():
                    salon_col = col
                    break

            # If no salon column found, try the 3rd column (common pattern)
            if salon_col is None and len(df.columns) >= 3:
                salon_col = df.columns[2]
                df = df.rename(columns={salon_col: 'SALONS'})

            if salon_col is not None:
                return df

        # Approach 3: Try with no header and assign column names
        df = pd.read_csv(file_path, header=None)

        # Typical structure of MTD files
        # Typical number of columns (S.NO, SALONS, 12 months)
        if df.shape[1] >= 14:
            # Extract header row (usually row 0 or 1)
            header_row = 0 if 'SALON' in str(df.iloc[0][2]).upper() else 1

            # Extract column names from the header row
            column_names = df.iloc[header_row].values

            # Clean up column names
            column_names = [str(name).strip() for name in column_names]

            # Set appropriate column names
            df.columns = column_names

            # Skip header rows
            df = df.iloc[header_row+1:].reset_index(drop=True)

            # Rename salon column if needed
            for col in df.columns:
                if 'SALON' in str(col).upper():
                    df = df.rename(columns={col: 'SALONS'})
                    break

            return df

        # If all approaches fail, return the original DataFrame
        st.warning(f"Using best-effort parsing for {file_path}")
        return df

    except Exception as e:
        st.error(f"Error reading file {file_path}: {e}")
        return pd.DataFrame()


# Add footer
st.markdown("---")
st.caption("Executive Dashboard - Created with Streamlit and Plotly")
