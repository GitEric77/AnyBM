# MOTOTRBO Zone Generator - Streamlit Frontend

This is a web-based frontend for the Anytone zone file generator that uses the BrandMeister API to retrieve DMR repeater information and generate zone files for Anytone DMR radios.

## Installation
If you want to host your own copy of the webapp you can leverage the userdata file to bootstrap a linux machine (I host on AWS using Amazon Linux 2023). In general the install is:
1. Ensure you have Python installed

2. Make sure you have all the required dependencies installed:
   ```
   pip install -r requirements_streamlit.txt
   ```

3. Run the Streamlit app:
   ```
   streamlit run app.py
   ```

4. The app will open in your default web browser at http://localhost:8501

## Features

- **User-friendly interface** for generating Anytone CPS files
- **Standard Mode** for creating a zone file with all repeaters
- **Talkgroup Mode** for creating a zone file with active talkgroups and respective channels
- **Download** generated CSV files and contacts.csv directly from the browser
- **Bulk Download** all generated files in a single ZIP archive
- **City Prefix** option to name channels with city abbreviation and talkgroup name
- **Unique Session IDs** for multiple users to work simultaneously
- **Visualize** zone file, channels, and talkgroup output in the web interface

## Usage

### Standard Mode
1. Enter a zone name
2. Select the band (VHF, UHF, or Both)
3. Choose a search type (MCC, QTH, or GPS)
4. Fill in the required fields based on your search type
5. Configure additional options as needed
6. Click "Generate Talkgroup Files"
7. Download the generated CSV file or as a ZIP archive

### Talkgroup Mode
1. Select the band (VHF, UHF. or Both)
2. Choose a search type (MCC, QTH, or GPS)
3. Fill in the required fields based on your search type
4. Optionally enable "Use city abbreviation prefix for channel names" to add city prefixes to channels Ex: BUR.MN State
5. Configure additional options as needed
6. Click "Generate Talkgroup Files"
7. Download the generated CSV files individually or as a ZIP archive

### Custom Talkgroup Template
1. Download the default talkgroup_template.csv
2. Modify the template with your preferred contact names (ensure to specify Group Call or Private Call)
3. Upload your modified template using the "Upload Custom Talkgroup Template"
4. Your custom template will be used when generating talkgroup files

### Importing to CPS
* Open CPS, go to `Tools -> Import'
* Select the generated talkgroups, channels, and zones csv files
* Import
