import streamlit as st
import subprocess
import os
import pandas as pd
from io import StringIO
import base64
import uuid
import hashlib
from datetime import datetime

st.set_page_config(page_title="Anytone Zone Generator", page_icon="📻", layout="wide")

# Function to generate a unique session ID for each user
def get_session_id():
    # Check if session_id exists in session state
    if 'session_id' not in st.session_state:
        # Generate a unique session ID based on timestamp and random UUID
        unique_id = f"{datetime.now().timestamp()}_{uuid.uuid4()}"
        # Hash the ID to make it shorter but still unique
        hashed_id = hashlib.md5(unique_id.encode()).hexdigest()
        # Store in session state
        st.session_state.session_id = hashed_id
    
    return st.session_state.session_id

# Get or create a unique session ID for the current user
session_id = get_session_id()

st.title("Anytone Zone Generator")
st.markdown("Generate Anytone zone files from BrandMeister repeater list")

# Create tabs for different modes
tab1, tab2 = st.tabs(["Standard Mode", "Talkgroup Mode"])

with tab1:
    st.header("Standard Mode")
    st.markdown("Create a single zone file with channels for each repeater timeslot")
    col1, col2 = st.columns(2)
    
    with col1:
        zone_name = st.text_input("Zone Name", help="Choose a name for your zone")
        band = st.selectbox("Band", ["vhf", "uhf", "both"], help="Select repeater band")
        
        search_type = st.selectbox("Search Type", ["mcc", "qth", "gps"], 
                                  help="Select repeaters by MCC code, QTH locator index or GPS coordinates")
        
        if search_type == "mcc":
            mcc = st.text_input("MCC Code or Country Code", 
                               help="First repeater ID digits (usually 3 digits MCC) or two letter country code")
        
        elif search_type == "qth":
            qth = st.text_input("QTH Locator", help="QTH locator index like KO26BX")
            
            # Add distance unit toggle
            distance_unit = st.radio("Distance Unit", ["km", "miles"], horizontal=True)
            
            if distance_unit == "km":
                radius = st.number_input("Radius (km)", min_value=1, value=100, 
                                        help="Area radius in kilometers around the center of the chosen QTH locator")
                st.text(f"Equivalent: {radius:.1f} km = {radius * 0.621371:.1f} miles")
            else:  # miles
                radius_miles = st.number_input("Radius (miles)", min_value=1, value=60, 
                                             help="Area radius in miles around the center of the chosen QTH locator")
                radius = radius_miles / 0.621371  # Convert miles to km for backend
                st.text(f"Equivalent: {radius_miles:.1f} miles = {radius:.1f} km")
        
        elif search_type == "gps":
            col_lat, col_lon = st.columns(2)
            with col_lat:
                latitude = st.number_input("Latitude", format="%.6f")
            with col_lon:
                longitude = st.number_input("Longitude", format="%.6f")
                
            # Add distance unit toggle
            distance_unit = st.radio("Distance Unit", ["km", "miles"], horizontal=True, key="gps_distance_unit")
            
            if distance_unit == "km":
                radius = st.number_input("Radius (km)", min_value=1, value=100, 
                                        help="Area radius in kilometers around the GPS coordinates")
                st.text(f"Equivalent: {radius:.1f} km = {radius * 0.621371:.1f} miles")
            else:  # miles
                radius_miles = st.number_input("Radius (miles)", min_value=1, value=60, 
                                             help="Area radius in miles around the GPS coordinates")
                radius = radius_miles / 0.621371  # Convert miles to km for backend
                st.text(f"Equivalent: {radius_miles:.1f} miles = {radius:.1f} km")
    
    with col2:
        force_download = st.checkbox("Force Download", 
                                    help="Forcibly download repeater list even if it exists locally")
        
        only_with_power = st.checkbox("Only with Power", 
                                     help="Only select repeaters with defined power")
        
        if only_with_power:
            min_power = st.number_input("Minimum Power (W)", min_value=1, value=10,
                                      help="Minimum power in watts")
        
        six_digit = st.checkbox("6-Digit ID Only", value=True,
                               help="Only select repeaters with 6 digit ID (real repeaters, not hotspots)")
        
        zone_capacity = st.number_input("Zone Capacity", min_value=1, value=160, 
                                       help="Channel capacity within zone. 160 by default for top models, use 16 for lite models")
        

        
        callsign_filter = st.text_input("Callsign Filter", 
                                       help="Only list callsigns containing specified string like a region number")
    
    if st.button("Generate Zone Files", key="generate_standard"):
        if search_type == "mcc" and not mcc:
            st.error("Please enter an MCC code or country code")
        elif search_type == "qth" and not qth:
            st.error("Please enter a QTH locator")
        elif search_type == "gps" and (latitude == 0 and longitude == 0):
            st.error("Please enter valid GPS coordinates")
        elif not zone_name:
            st.error("Please enter a zone name")
        else:
            # Build command with user-specific output directory
            user_output_dir = f"output_{session_id}"
            cmd = ["python", "zone.py", "-n", zone_name, "-b", band, "-t", search_type, "-o", user_output_dir]
            
            if force_download:
                cmd.extend(["-f"])
            
            if search_type == "mcc":
                cmd.extend(["-m", mcc])
            elif search_type == "qth":
                # Always pass radius in km to the backend as an integer
                cmd.extend(["-q", qth, "-r", str(int(radius))])
            elif search_type == "gps":
                # Handle negative coordinates using the format from README example
                if latitude < 0:
                    cmd.extend([f"-lat=-{abs(latitude)}"])
                else:
                    cmd.extend(["-lat", str(latitude)])
                
                # Use the -lon=VALUE format for negative longitude values
                if longitude < 0:
                    cmd.extend([f"-lon=-{abs(longitude)}"])
                else:
                    cmd.extend(["-lon", str(longitude)])
                
                # Always pass radius in km to the backend as an integer
                cmd.extend(["-r", str(int(radius))])
            
            if only_with_power:
                cmd.extend(["-p", str(min_power)])
            
            if six_digit:
                cmd.extend(["-6"])
            
            cmd.extend(["-zc", str(zone_capacity)])
            

            
            if callsign_filter:
                cmd.extend(["-cs", callsign_filter])
            
            # Show command
            cmd_str = " ".join(cmd)
            st.code(cmd_str, language="bash")
            
            # Run command
            with st.spinner("Generating zone files..."):
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
                output, error = process.communicate()
                
                if process.returncode == 0:
                    st.success("Zone files generated successfully!")
                    st.code(output)
                    
                    # Find generated CSV files in user-specific output directory
                    output_dir = f"output_{session_id}"
                    if not os.path.exists(output_dir):
                        os.makedirs(output_dir)
                    csv_files = [f for f in os.listdir(output_dir) if f.endswith('.csv')]
                    
                    if csv_files:
                        st.subheader("Download Generated Files")
                        
                        # Create a zip file with all CSV files
                        import io
                        import zipfile
                        
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                            for csv_file in csv_files:
                                file_path = os.path.join(output_dir, csv_file)
                                with open(file_path, "r", newline='') as file:
                                    zip_file.writestr(csv_file, file.read())
                        
                        # Create download button for the zip file
                        zip_buffer.seek(0)
                        zip_bytes = zip_buffer.getvalue()
                        zip_filename = f"Anytone_files_{session_id[:8]}.zip"
                        st.download_button(
                            label="📦 Download All Files as ZIP",
                            data=zip_bytes,
                            file_name=zip_filename,
                            mime="application/zip",
                            key="download_standard_zip"
                        )
                        
                        # Horizontal line to separate individual file downloads
                        st.markdown("---")
                        st.markdown("Or download individual files:")
                        
                        # CSV file downloads
                        for csv_file in csv_files:
                            file_path = os.path.join(output_dir, csv_file)
                            with open(file_path, "r", newline='') as file:
                                file_content = file.read()
                                
                            b64 = base64.b64encode(file_content.encode()).decode()
                            href = f'<a href="data:text/csv;base64,{b64}" download="{csv_file}">Download {csv_file}</a>'
                            st.markdown(href, unsafe_allow_html=True)
                    

                else:
                    st.error("Error generating zone files")
                    st.code(error)

with tab2:
    st.header("Talkgroup Mode")
    st.markdown("Create a zone file for each repeater with channels for talkgroups on the timeslots")
    
    # Create user-specific output directory using session ID
    user_output_dir = f"output_{session_id}"
    if not os.path.exists(user_output_dir):
        os.makedirs(user_output_dir)
    
    # Create download link for talkgroups_template.csv
    template_href = ""
    if os.path.exists("talkgroups_template.csv"):
        with open("talkgroups_template.csv", "r", newline='') as file:
            template_content = file.read()
        template_b64 = base64.b64encode(template_content.encode()).decode()
        template_href = f'<a href="data:text/csv;base64,{template_b64}" download="talkgroups_template.csv">talkgroups_template.csv</a>'
    
    # Add file uploader for custom talkgroups template
    st.subheader("Upload Custom Talkgroups Template")
    st.markdown(f"Download and modify the {template_href} file if you want talkgroups named differently than Brandmeister", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload your own talkgroups_template.csv", type="csv", key="tg_template_upload")
    if uploaded_file is not None:
        # Create user-specific talkgroups_uploads directory
        user_uploads_dir = f"talkgroups_uploads_{session_id}"
        if not os.path.exists(user_uploads_dir):
            os.makedirs(user_uploads_dir)
        
        # Save the uploaded file to user-specific directory
        template_path = os.path.join(user_uploads_dir, "talkgroups_template.csv")
        with open(template_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("Custom talkgroups template uploaded successfully!")
        
        # Display the uploaded file as a dataframe
        try:
            df = pd.read_csv(uploaded_file)
            st.dataframe(df, height=200)
        except:
            st.warning("Could not display the uploaded file as a table")
    
    st.subheader("Channel Naming")
    use_city_prefix = st.checkbox("Use city abbreviation prefix for channel names", 
                                help="Prefix channel names with 3-character city abbreviation (e.g. 'NYC.TG123')")
    
    st.subheader("Search Settings")
    col1, col2 = st.columns(2)
    
    with col1:
        band_tg = st.selectbox("Band", ["vhf", "uhf", "both"], help="Select repeater band", key="band_tg")
        
        search_type_tg = st.selectbox("Search Type", ["mcc", "qth", "gps"], 
                                     help="Select repeaters by MCC code, QTH locator index or GPS coordinates",
                                     key="search_type_tg")
        
        if search_type_tg == "mcc":
            mcc_tg = st.text_input("MCC Code or Country Code", 
                                  help="First repeater ID digits (usually 3 digits MCC) or two letter country code",
                                  key="mcc_tg")
        
        elif search_type_tg == "qth":
            qth_tg = st.text_input("QTH Locator", help="QTH locator index like KO26BX", key="qth_tg")
            
            # Add distance unit toggle
            distance_unit_tg = st.radio("Distance Unit", ["km", "miles"], horizontal=True, key="qth_tg_distance_unit")
            
            if distance_unit_tg == "km":
                radius_tg = st.number_input("Radius (km)", min_value=1, value=100, 
                                           help="Area radius in kilometers around the center of the chosen QTH locator",
                                           key="radius_tg")
                st.text(f"Equivalent: {radius_tg:.1f} km = {radius_tg * 0.621371:.1f} miles")
            else:  # miles
                radius_miles_tg = st.number_input("Radius (miles)", min_value=1, value=60, 
                                                help="Area radius in miles around the center of the chosen QTH locator",
                                                key="radius_miles_tg")
                radius_tg = radius_miles_tg / 0.621371  # Convert miles to km for backend
                st.text(f"Equivalent: {radius_miles_tg:.1f} miles = {radius_tg:.1f} km")
        
        elif search_type_tg == "gps":
            col_lat_tg, col_lon_tg = st.columns(2)
            with col_lat_tg:
                latitude_tg = st.number_input("Latitude", format="%.6f", key="latitude_tg")
            with col_lon_tg:
                longitude_tg = st.number_input("Longitude", format="%.6f", key="longitude_tg")
                
            # Add distance unit toggle
            distance_unit_tg = st.radio("Distance Unit", ["km", "miles"], horizontal=True, key="gps_tg_distance_unit")
            
            if distance_unit_tg == "km":
                radius_tg = st.number_input("Radius (km)", min_value=1, value=100, 
                                           help="Area radius in kilometers around the GPS coordinates",
                                           key="radius_tg")
                st.text(f"Equivalent: {radius_tg:.1f} km = {radius_tg * 0.621371:.1f} miles")
            else:  # miles
                radius_miles_tg = st.number_input("Radius (miles)", min_value=1, value=60, 
                                                help="Area radius in miles around the GPS coordinates",
                                                key="radius_miles_tg")
                radius_tg = radius_miles_tg / 0.621371  # Convert miles to km for backend
                st.text(f"Equivalent: {radius_miles_tg:.1f} miles = {radius_tg:.1f} km")
    
    with col2:
        force_download_tg = st.checkbox("Force Download", 
                                       help="Forcibly download repeater list even if it exists locally",
                                       key="force_download_tg")
        
        only_with_power_tg = st.checkbox("Only with Power", 
                                        help="Only select repeaters with defined power",
                                        key="only_with_power_tg")
        
        if only_with_power_tg:
            min_power_tg = st.number_input("Minimum Power (W)", min_value=1, value=10,
                                         help="Minimum power in watts", key="min_power_tg")
        
        six_digit_tg = st.checkbox("6-Digit ID Only", value=True,
                                  help="Only select repeaters with 6 digit ID (real repeaters, not hotspots)",
                                  key="six_digit_tg")
        
        callsign_filter_tg = st.text_input("Callsign Filter", 
                                          help="Only list callsigns containing specified string like a region number",
                                          key="callsign_filter_tg")
    
    if st.button("Generate Talkgroup Files", key="generate_talkgroup"):
        if search_type_tg == "mcc" and not mcc_tg:
            st.error("Please enter an MCC code or country code")
        elif search_type_tg == "qth" and not qth_tg:
            st.error("Please enter a QTH locator")
        elif search_type_tg == "gps" and (latitude_tg == 0 and longitude_tg == 0):
            st.error("Please enter valid GPS coordinates")
        else:
            # Build command with user-specific output directory
            user_output_dir = f"output_{session_id}"
            cmd = ["python", "zone.py", "-b", band_tg, "-t", search_type_tg, "-tg", "-o", user_output_dir]
            
            # Add city prefix option if selected
            if use_city_prefix:
                cmd.extend(["--city-prefix"])
            
            if force_download_tg:
                cmd.extend(["-f"])
            
            if search_type_tg == "mcc":
                cmd.extend(["-m", mcc_tg])
            elif search_type_tg == "qth":
                # Always pass radius in km to the backend as an integer
                cmd.extend(["-q", qth_tg, "-r", str(int(radius_tg))])
            elif search_type_tg == "gps":
                # Handle negative coordinates using the format from README example
                if latitude_tg < 0:
                    cmd.extend([f"-lat=-{abs(latitude_tg)}"])
                else:
                    cmd.extend(["-lat", str(latitude_tg)])
                
                # Use the -lon=VALUE format for negative longitude values
                if longitude_tg < 0:
                    cmd.extend([f"-lon=-{abs(longitude_tg)}"])
                else:
                    cmd.extend(["-lon", str(longitude_tg)])
                
                # Always pass radius in km to the backend as an integer
                cmd.extend(["-r", str(int(radius_tg))])
            
            if only_with_power_tg:
                cmd.extend(["-p", str(min_power_tg)])
            
            if six_digit_tg:
                cmd.extend(["-6"])
            
            if callsign_filter_tg:
                cmd.extend(["-cs", callsign_filter_tg])
            
            # Show command
            cmd_str = " ".join(cmd)
            st.code(cmd_str, language="bash")
            
            # Run command
            with st.spinner("Generating talkgroup files..."):
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
                output, error = process.communicate()
                
                if process.returncode == 0:
                    st.success("Talkgroup files generated successfully!")
                    st.code(output)
                    
                    # Find generated CSV files in user-specific output directory
                    output_dir = f"output_{session_id}"
                    if not os.path.exists(output_dir):
                        os.makedirs(output_dir)
                    csv_files = [f for f in os.listdir(output_dir) if f.endswith('.csv')]
                    
                    if csv_files:
                        st.subheader("Download Generated Files")
                        
                        # Create a zip file with all CSV files
                        import io
                        import zipfile
                        
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                            for csv_file in csv_files:
                                file_path = os.path.join(output_dir, csv_file)
                                with open(file_path, "r", newline='') as file:
                                    zip_file.writestr(csv_file, file.read())
                        
                        # Create download button for the zip file
                        zip_buffer.seek(0)
                        zip_bytes = zip_buffer.getvalue()
                        zip_filename = f"anybmfiles_{session_id[:8]}.zip"
                        st.download_button(
                            label="📦 Download All Files as ZIP",
                            data=zip_bytes,
                            file_name=zip_filename,
                            mime="application/zip",
                            key="download_all_zip"
                        )
                        
                        # Horizontal line to separate individual file downloads
                        st.markdown("---")
                        st.markdown("Or download individual files:")
                        
                        # CSV file downloads with preview
                        for csv_file in csv_files:
                            file_path = os.path.join(output_dir, csv_file)
                            
                            # Display CSV as a table
                            st.subheader(f"{csv_file}")
                            try:
                                df = pd.read_csv(file_path)
                                st.dataframe(df)
                            except:
                                st.warning(f"Could not display {csv_file} as a table")
                            
                            # Provide download link
                            with open(file_path, "r", newline='') as file:
                                file_content = file.read()
                                
                            b64 = base64.b64encode(file_content.encode()).decode()
                            href = f'<a href="data:text/csv;base64,{b64}" download="{csv_file}">Download {csv_file}</a>'
                            st.markdown(href, unsafe_allow_html=True)
                    
                    # Clean up user-specific talkgroups_uploads directory
                    talkgroups_uploads_dir = f"talkgroups_uploads_{session_id}"
                    if os.path.exists(talkgroups_uploads_dir):
                        for file in os.listdir(talkgroups_uploads_dir):
                            file_path = os.path.join(talkgroups_uploads_dir, file)
                            try:
                                if os.path.isfile(file_path):
                                    os.unlink(file_path)
                            except Exception as e:
                                st.warning(f"Error deleting {file_path}: {e}")
                else:
                    st.error("Error generating talkgroup files")
                    st.code(error)

# Help section
st.sidebar.header("Help")

st.sidebar.markdown("""
## How to use
This was tested with Anytone CPS 3.08. Anytone is known to change csv structure so other versions may not work as expected.
[Demo Video](https://youtu.be/cRO7uoUekoY)
1. Choose between Standard Mode or Talkgroup Mode
2. Fill in the required fields
3. In Talkgroup Mode, upload a talkgroups template (optional)
4. Click the Generate button
5. Download the generated files

""", unsafe_allow_html=True)

st.sidebar.markdown("""
## CSV Files Generated
- **channels.csv**: Channel configuration data
- **zones.csv**: Zone assignment data  
- **talkgroups.csv**: Contact/talkgroup data (Talkgroup Mode)
- Import these files into your radio programming software as needed
""")

# About section
st.sidebar.header("About")
st.sidebar.markdown("""
Anytone Zone Generator uses the [BrandMeister API](https://wiki.brandmeister.network/index.php/API/Halligan_API) to retrieve DMR repeater information and generate zone files for Anytone DMR radios.
[View on GitHub](https://github.com/GitEric77/AnyBM)
""")

# Display session ID in sidebar for debugging (can be removed in production)
st.sidebar.header("Session Info")
st.sidebar.text(f"Session ID: {session_id[:8]}...")