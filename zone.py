#!/usr/bin/env python3

import argparse
import json
from os.path import exists
from tabulate import tabulate

import geopy.distance
import maidenhead
import mobile_codes
import requests
import urllib3


parser = argparse.ArgumentParser(description='Generate MOTOTRBO zone files from BrandMeister.')

parser.add_argument('-f', '--force', action='store_true',
                    help='Forcibly download repeater list even if it exists locally.')
parser.add_argument('-n', '--name', required=False, help='Zone name. Choose it freely on your own. Required unless using -tg argument.')
parser.add_argument('-b', '--band', choices=['vhf', 'uhf', 'both'], required=True, help='Repeater band.')

parser.add_argument('-t', '--type', choices=['mcc', 'qth', 'gps'], required=True,
                    help='Select repeaters by MCC code, QTH locator index or GPS coordinates.')

parser.add_argument('-m', '--mcc', help='First repeater ID digits, usually a 3 digits MCC. '
                                        'You can also use a two letter country code instead.')
parser.add_argument('-q', '--qth', help='QTH locator index like KO26BX.')

parser.add_argument('-r', '--radius', default=100, type=int,
                    help='Area radius in kilometers around the center of the chosen QTH locator. Defaults to 100.')

parser.add_argument('-lat', type=float, help='Latitude of a GPS position.')
parser.add_argument('-lon', type=float, help='Longitude of a GPS position.')

parser.add_argument('-p', '--pep', nargs='?', const='0', help='Only select repeaters with defined power. Optional value specifies minimum power in watts.')
parser.add_argument('-6', '--six', action='store_true', help='Only select repeaters with 6 digit ID.')
parser.add_argument('-zc', '--zone-capacity', default=160, type=int,
                    help='Channel capacity within zone. 160 by default as for top models, use 16 for the lite and '
                         'non-display ones.')

parser.add_argument('-cs', '--callsign', help='Only list callsigns containing specified string like a region number.')
parser.add_argument('-tg', '--talkgroups', action='store_true',
                    help='Create channels only for active talkgroups on repeaters (no channels with blank contact ID).')
parser.add_argument('-o', '--output', default='output',
                    help='Output directory for generated files. Default is "output".')
parser.add_argument('--city-prefix', action='store_true',
                    help='Prefix channel names with 3-character city abbreviation (e.g. "NYC.TG123")')


args = parser.parse_args()

# Validate that name is provided if not using talkgroups mode
if not args.name and not args.talkgroups:
    parser.error("the -n/--name argument is required when not using -tg/--talkgroups")


bm_url = 'https://api.brandmeister.network/v2/device'
bm_file = 'BM.json'
filtered_list = []
output_list = []
existing = {}


if args.type == 'qth':
    qth_coords = maidenhead.to_location(args.qth, center=True)
if args.type == 'gps':
    qth_coords = (args.lat, args.lon)

if args.mcc and not str(args.mcc).isdigit():
    args.mcc = mobile_codes.alpha2(args.mcc)[4]





def download_file():
    if not exists(bm_file) or args.force:
        print(f'Downloading from {bm_url}')

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        response = requests.get(bm_url, verify=False)
        response.raise_for_status()

        with open(bm_file, 'wb') as file:
            file.write(response.content)

        print(f'Saved to {bm_file}')


def check_distance(loc1, loc2):
    return geopy.distance.great_circle(loc1, loc2).km


def filter_list():
    global filtered_list
    global existing
    global qth_coords

    f = open(bm_file, "r")

    json_list = json.loads(f.read())
    sorted_list = sorted(json_list, key=lambda k: (k['callsign'], int(k["id"])))

    for item in sorted_list:
        if args.band != 'both':
            if not ((args.band == 'vhf' and item['rx'].startswith('1')) or (
                    args.band == 'uhf' and item['rx'].startswith('4'))):
                continue

        if args.type == 'mcc':
            is_starts = False

            if type(args.mcc) is list:
                for mcc in args.mcc:
                    if str(item['id']).startswith(mcc):
                        is_starts = True
            else:
                if str(item['id']).startswith(args.mcc):
                    is_starts = True

            if not is_starts:
                continue

        if (args.type == 'qth' or args.type == 'gps') and check_distance(qth_coords,
                                                                         (item['lat'], item['lng'])) > args.radius:
            continue

        if args.pep:
            # Skip if power is not defined or is zero
            if not str(item['pep']).isdigit() or str(item['pep']) == '0':
                continue
            # Skip if power is less than specified minimum (if provided)
            if args.pep != '0' and int(item['pep']) < int(args.pep):
                continue

        if args.six and not len(str(item['id'])) == 6:
            continue

        if args.callsign and (not args.callsign in item['callsign']):
            continue

        if item['callsign'] == '':
            item['callsign'] = item['id']

        item['callsign'] = item['callsign'].split()[0]

        if any((existing['rx'] == item['rx'] and existing['tx'] == item['tx'] and existing['callsign'] == item[
            'callsign']) for existing in filtered_list):
            continue

        if not item['callsign'] in existing: existing[item['callsign']] = 0
        existing[item['callsign']] += 1
        item['turn'] = existing[item['callsign']]

        filtered_list.append(item)

    f.close()


def get_talkgroup_channels(repeater_id):
    """
    Get talkgroups for a specific repeater from BrandMeister API
    
    Args:
        repeater_id (int): Repeater ID
        
    Returns:
        list: List of talkgroup IDs configured for this repeater
    """
    try:
        url = f'https://api.brandmeister.network/v2/device/{repeater_id}/talkgroup'
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(url, verify=False)
        response.raise_for_status()
        talkgroups_data = response.json()
        
        # Extract talkgroup IDs
        tg_ids = []
        for tg in talkgroups_data:
            if 'talkgroup' in tg and tg.get('slot') is not None:
                tg_ids.append((tg['talkgroup'], tg['slot']))
        
        return tg_ids
    except Exception as e:
        print(f"Error fetching talkgroups for repeater {repeater_id}: {e}")
        return []


def format_talkgroup_channel(item, tg_id, timeslot):
    """Add talkgroup channel to output list"""
    global output_list
    
    # Add to output list for display (swap rx/tx for radio perspective)
    output_list.append([item['callsign'], item['tx'], item['rx'], item['colorcode'], item['city'], item['last_seen'],
                        f"https://brandmeister.network/?page=repeater&id={item['id']} TG{tg_id}"])


def format_channel(item):
    global output_list

    # Create city abbreviation
    city = item['city'].split(',')[0].strip()
    city_abbr = city[:3].upper() if len(city) >= 3 else (city + 'XXX')[:3].upper()
    
    # Create channels for both timeslots
    for slot in [1, 2]:
        # Ensure channel name fits in 16 characters with TS suffix
        base_name = f"{item['callsign']}.{city_abbr}"
        ts_suffix = f" TS{slot}"
        if len(base_name + ts_suffix) > 16:
            # Truncate callsign to fit
            max_callsign_len = 16 - len(f".{city_abbr}{ts_suffix}")
            truncated_callsign = item['callsign'][:max_callsign_len]
            ch_alias = f"{truncated_callsign}.{city_abbr}{ts_suffix}"
        else:
            ch_alias = base_name + ts_suffix
        
        output_list.append([ch_alias, item['tx'], item['rx'], item['colorcode'], item['city'], item['last_seen'],
                            f"https://brandmeister.network/?page=repeater&id={item['id']}"])


def cleanup_contact_uploads():
    """Delete files in the contact_uploads directory after processing"""
    import os
    
    # Clean up regular contact_uploads directory
    if exists('contact_uploads'):
        for file in os.listdir('contact_uploads'):
            file_path = os.path.join('contact_uploads', file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                    print(f"Deleted {file_path}")
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
    
    # Clean up user-specific contact_uploads directories
    for dir_name in os.listdir('.'):
        if dir_name.startswith('contact_uploads_'):
            for file in os.listdir(dir_name):
                file_path = os.path.join(dir_name, file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                        print(f"Deleted {file_path}")
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")


def process_channels():
    global output_list

    if args.talkgroups:
        # Collect all unique talkgroup IDs first
        unique_talkgroups = set()
        
        # First pass: collect all talkgroup IDs
        for item in filtered_list:
            try:
                tg_channels = get_talkgroup_channels(item['id'])
                for tg_id, slot in tg_channels:
                    unique_talkgroups.add(tg_id)
            except Exception as e:
                print(f"Error collecting talkgroups for {item['callsign']}: {e}")
        
        # Process talkgroups.csv first to ensure it exists with all needed talkgroups
        try:
            import csv
            import time
            import os
            import shutil
            
            # Create output directory if it doesn't exist
            if not os.path.exists(args.output):
                os.makedirs(args.output)
            
            talkgroups_file = os.path.join(args.output, 'talkgroups.csv')
            
            # Check for custom template in user-specific talkgroups_uploads directory first
            user_uploads_dir = None
            for dir_name in os.listdir('.'):
                if dir_name.startswith('talkgroups_uploads_'):
                    user_uploads_dir = dir_name
                    break
                    
            if user_uploads_dir:
                custom_template = os.path.join(user_uploads_dir, 'talkgroups_template.csv')
                if exists(custom_template):
                    try:
                        shutil.copy(custom_template, talkgroups_file)
                        print(f"Copied custom talkgroups_template.csv from {user_uploads_dir} to {talkgroups_file}")
                    except Exception as e:
                        print(f"Error copying custom talkgroups template from {user_uploads_dir}: {e}")
            
            # Fall back to default template if no custom template exists
            if not exists(talkgroups_file) and exists('talkgroups_template.csv'):
                try:
                    shutil.copy('talkgroups_template.csv', talkgroups_file)
                    print(f"Copied default talkgroups_template.csv to {talkgroups_file}")
                except Exception as e:
                    print(f"Error copying default talkgroups template: {e}")
            
            # Read the existing CSV file
            with open(talkgroups_file, 'r', newline='') as csvfile:
                reader = csv.reader(csvfile)
                rows = list(reader)
            
            # Keep the header rows (first 2 rows)
            header_rows = rows[:2]
            template_row = rows[2] if len(rows) > 2 else [''] * len(header_rows[0])
            
            # Get existing talkgroup IDs to avoid duplicates (check column B for Radio ID)
            existing_tg_ids = set()
            for row in rows[1:]:  # Skip header row
                if len(row) > 1 and row[1]:  # Check if column B (Radio ID) has a value
                    existing_tg_ids.add(row[1])
            
            # Create new rows with talkgroup data
            new_rows = []
            for tg_id in sorted(unique_talkgroups):
                # Extract only numeric characters from talkgroup ID
                numeric_tg_id = ''.join(c for c in str(tg_id) if c.isdigit())
                if numeric_tg_id and numeric_tg_id not in existing_tg_ids:  # Only add if not already in contacts
                    # Fetch talkgroup name from BrandMeister API
                    tg_name = None
                    try:
                        print(f"Fetching name for TG {numeric_tg_id}...", end="", flush=True)
                        url = f'https://api.brandmeister.network/v2/talkgroup/{numeric_tg_id}'
                        response = requests.get(url, verify=False)
                        response.raise_for_status()
                        data = response.json()
                        if 'Name' in data and data['Name']:
                            tg_name = data['Name'].rstrip()
                            print(f" Found: {data['Name']}")
                        else:
                            tg_name = numeric_tg_id  # Fallback to ID if no name
                            print(" No name found")
                        time.sleep(0.2)  # Be nice to the API
                    except Exception as api_error:
                        print(f"\nError fetching name for TG {numeric_tg_id}: {api_error}")
                        tg_name = numeric_tg_id  # Fallback to ID if API fails
                    
                    # Create new row in talkgroups.csv format: [No., Radio ID, Name, Call Type, Call Alert]
                    new_row = [len(rows) + len(new_rows), numeric_tg_id, tg_name, 'Group Call', 'None']
                    new_rows.append(new_row)
            
            # Write the updated CSV file with existing entries plus new ones
            with open(talkgroups_file, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile, lineterminator='\r\n')
                # For talkgroups template format, write header and all rows
                if len(header_rows) == 1:  # Simple talkgroups format
                    writer.writerows(header_rows)
                    writer.writerows(rows[1:])  # Write existing template entries
                    writer.writerows(new_rows)  # Append new unique entries
                else:  # Complex contact format
                    writer.writerows(header_rows)
                    writer.writerows(rows[2:])  # Write existing entries after headers
                    writer.writerows(new_rows)  # Append new unique entries
            
            print(f"Updated {talkgroups_file} with {len(new_rows)} new unique talkgroups (total: {len(rows[2:]) + len(new_rows)})")
        except Exception as e:
            print(f"Error updating talkgroups.csv: {e}")
        
        # Now create channels using the updated talkgroups.csv
        output_list = []  # Global output list for all channels
        for item in filtered_list:
            try:
                tg_channels = get_talkgroup_channels(item['id'])
                if not tg_channels:
                    continue  # Skip repeaters with no talkgroups
                    
                for tg_id, slot in tg_channels:
                    format_talkgroup_channel(item, tg_id, slot)
                
                # Use city name for zone name
                city = item['city'].split(',')[0].strip()
                callsign = item['callsign']
                
                # Create filename (can be longer)
                filename = f"{callsign}_{city.replace(' ', '_')}"
                
                # Create zone alias (must be 16 chars or less)
                if len(callsign) + 1 >= 16:
                    # If callsign is already too long, just use it
                    zone_alias = callsign[:16]
                else:
                    # Use remaining space for city
                    city_max_len = 15 - len(callsign)
                    city_abbr = city.replace(' ', '')[:city_max_len]
                    zone_alias = f"{callsign}_{city_abbr}"
                # Ensure it's exactly 16 chars or less
                zone_alias = zone_alias[:16]
                
            except Exception as e:
                print(f"Error processing talkgroups for {item['callsign']}: {e}")
        
        # Show complete list of all channels after processing all repeaters
        if output_list:
            print('\n',
                  tabulate(output_list, headers=['Callsign', 'RX', 'TX', 'CC', 'City', 'Last seen', 'URL'],
                           disable_numparse=True),
                  '\n')
        

    else:
        # Original behavior for non-talkgroup mode
        channel_chunks = [filtered_list[i:i + args.zone_capacity] for i in range(0, len(filtered_list), args.zone_capacity)]
        chunk_number = 0

        for chunk in channel_chunks:
            chunk_number += 1
            output_list = []

            for item in chunk:
                format_channel(item)

            print('\n',
                  tabulate(output_list, headers=['Callsign', 'RX', 'TX', 'CC', 'City', 'Last seen', 'URL'],
                           disable_numparse=True),
                  '\n')

            if len(channel_chunks) == 1:
                zone_alias = args.name
            else:
                zone_alias = f'{args.name} #{chunk_number}'

def write_channels_csv():
    """Write channels data to channels.csv"""
    import csv
    import os
    
    channels_file = os.path.join(args.output, 'channels.csv')
    
    with open(channels_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, lineterminator='\r\n')
        # Write header based on updated channels.csv structure
        writer.writerow(['No.', 'Channel Name', 'Receive Frequency', 'Transmit Frequency', 'Channel Type', 
                        'Transmit Power', 'Band Width', 'CTCSS/DCS Decode', 'CTCSS/DCS Encode', 'Contact', 
                        'Contact Call Type', 'Contact TG/DMR ID', 'Radio ID', 'Busy Lock/TX Permit', 'Squelch Mode', 
                        'Optional Signal', 'DTMF ID', '2Tone ID', '5Tone ID', 'PTT ID', 'RX Color Code', 'Slot', 
                        'Scan List', 'Receive Group List', 'PTT Prohibit', 'Reverse', 'Simplex TDMA', 'Slot Suit', 
                        'AES Digital Encryption', 'Digital Encryption', 'Call Confirmation', 'Talk Around(Simplex)', 
                        'Work Alone', 'Custom CTCSS', '2TONE Decode', 'Ranging', 'Through Mode', 'APRS RX', 
                        'Analog APRS PTT Mode', 'Digital APRS PTT Mode', 'APRS Report Type', 'Digital APRS Report Channel', 
                        'Correct Frequency[Hz]', 'SMS Confirmation', 'Exclude channel from roaming', 'DMR MODE', 
                        'DataACK Disable', 'R5toneBot', 'R5ToneEot', 'Auto Scan', 'Ana Aprs Mute', 'Send Talker Alias', 
                        'AnaAprsTxPath', 'ARC4', 'ex_emg_kind', 'TxCC'])
        
        # Write channel data from output_list
        for i, channel in enumerate(output_list, 1):
            # Extract data from output_list format: [callsign, rx, tx, cc, city, last_seen, url]
            channel_name = channel[0]
            rx_freq = channel[1]
            tx_freq = channel[2]
            color_code = channel[3]
            
            # Extract talkgroup info from URL if in talkgroup mode
            contact_name = 'Simplex'
            tg_id = '99'
            if args.talkgroups and len(channel) > 6 and 'TG' in channel[6]:
                # Extract TG number from URL
                url_parts = channel[6].split('TG')
                if len(url_parts) > 1:
                    tg_id = url_parts[1].strip()
                    # Get contact name from talkgroups.csv first
                    try:
                        talkgroups_file = os.path.join(args.output, 'talkgroups.csv')
                        if os.path.exists(talkgroups_file):
                            with open(talkgroups_file, 'r', newline='') as cf:
                                reader = csv.reader(cf)
                                next(reader)  # Skip header row
                                for row in reader:
                                    if len(row) > 2 and row[1] == tg_id and row[2]:  # Column B=Radio ID, Column C=Name
                                        contact_name = row[2][:16].rstrip()
                                        break
                    except Exception:
                        pass
                    
                    # If not found in talkgroups.csv, try BrandMeister API
                    if contact_name == 'Simplex':
                        try:
                            url = f'https://api.brandmeister.network/v2/talkgroup/{tg_id}'
                            response = requests.get(url, verify=False)
                            response.raise_for_status()
                            data = response.json()
                            if 'Name' in data and data['Name']:
                                contact_name = data['Name'][:16].rstrip()
                        except Exception:
                            pass
                    
                    # Set channel name based on contact name
                    if contact_name != 'Simplex':
                        if args.city_prefix:
                            # Get city from filtered_list
                            for item in filtered_list:
                                if item['tx'] == rx_freq and item['rx'] == tx_freq:
                                    city = item['city'].split(',')[0].strip()
                                    city_abbr = city[:3].upper() if len(city) >= 3 else (city + 'XXX')[:3].upper()
                                    channel_name = f"{city_abbr}.{contact_name}"[:16].rstrip()
                                    break
                        else:
                            channel_name = contact_name.rstrip()
                    
                    # If no talkgroup name found, use talkgroup number
                    if contact_name == 'Simplex':
                        tg_name = tg_id  # Use just the number to match talkgroups.csv
                        if args.city_prefix:
                            # Get city from filtered_list
                            for item in filtered_list:
                                if item['tx'] == rx_freq and item['rx'] == tx_freq:
                                    city = item['city'].split(',')[0].strip()
                                    city_abbr = city[:3].upper() if len(city) >= 3 else (city + 'XXX')[:3].upper()
                                    channel_name = f"{city_abbr}.{tg_name}"[:16].rstrip()
                                    break
                        else:
                            channel_name = tg_name.rstrip()
                        contact_name = tg_name
            
            # Determine slot
            if args.talkgroups and len(channel) > 6 and 'TG' in channel[6]:
                # Get slot from repeater talkgroup data
                slot = '1'  # Default
                for item in filtered_list:
                    if item['tx'] == rx_freq and item['rx'] == tx_freq:
                        try:
                            tg_channels = get_talkgroup_channels(item['id'])
                            for tg_id_api, slot_api in tg_channels:
                                if str(tg_id_api) == tg_id:
                                    slot = str(slot_api)
                                    break
                        except Exception:
                            pass
                        break
            else:
                # Standard mode: extract slot from channel name
                if 'TS1' in channel_name:
                    slot = '1'
                elif 'TS2' in channel_name:
                    slot = '2'
                else:
                    slot = '1'
            
            # Write row with proper contact data and scan list set to None
            writer.writerow([i, channel_name, rx_freq, tx_freq, 'D-Digital', 'Turbo', '12.5K', 'Off', 'Off', 
                           contact_name, 'Group Call', tg_id, '', 'Always', 'Carrier', 'Off', '1', '1', '1', 'Off', 
                           color_code, slot, 'None', 'None', 'Off', 'Off', 'Off', 'Off', 'Normal Encryption', 
                           'Off', 'Off', 'Off', 'Off', '0', '1', 'Off', 'Off', 'Off', 'Off', 'Off', 'Off', '1', 
                           '1', 'Off', '0', '1', '0', '0', '0', '0', '0', '0', '0', '0', '0', color_code])
    
    print(f'Channels CSV file "{channels_file}" written.')


def write_zones_csv():
    """Write zones data to zones.csv"""
    import csv
    import os
    
    zones_file = os.path.join(args.output, 'zones.csv')
    
    with open(zones_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, lineterminator='\r\n')
        # Write header based on updated zones.csv structure
        writer.writerow(['No.', 'Zone Name', 'Zone Channel Member', 'Zone Channel Member RX Frequency', 
                        'Zone Channel Member TX Frequency', 'A Channel', 'A Channel RX Frequency', 
                        'A Channel TX Frequency', 'B Channel', 'B Channel RX Frequency', 'B Channel TX Frequency', 
                        'Zone Hide'])
        
        if args.talkgroups:
            # For talkgroup mode, create one zone per repeater
            zone_num = 1
            for item in filtered_list:
                try:
                    tg_channels = get_talkgroup_channels(item['id'])
                    if not tg_channels:
                        continue
                    
                    city = item['city'].split(',')[0].strip()
                    callsign = item['callsign']
                    zone_name = f"{callsign}_{city.replace(' ', '_')}"
                    
                    # Collect channel names and frequencies
                    channel_names = []
                    rx_freqs = []
                    tx_freqs = []
                    
                    # Get channel names from channels.csv for this repeater
                    channels_file = os.path.join(args.output, 'channels.csv')
                    if os.path.exists(channels_file):
                        with open(channels_file, 'r', newline='') as cf:
                            reader = csv.reader(cf)
                            next(reader)  # Skip header
                            for row in reader:
                                if len(row) > 3 and row[2] == str(item['tx']) and row[3] == str(item['rx']):
                                    channel_names.append(row[1])  # Channel Name
                                    rx_freqs.append(item['tx'])
                                    tx_freqs.append(item['rx'])
                    
                    # Write zone row with Zone Hide column
                    writer.writerow([zone_num, zone_name[:16], '|'.join(channel_names), '|'.join(rx_freqs), 
                                   '|'.join(tx_freqs), channel_names[0] if channel_names else '', 
                                   rx_freqs[0] if rx_freqs else '', tx_freqs[0] if tx_freqs else '',
                                   channel_names[0] if channel_names else '', 
                                   rx_freqs[0] if rx_freqs else '', tx_freqs[0] if tx_freqs else '', '0'])
                    zone_num += 1
                except Exception as e:
                    print(f"Error processing zone for {item['callsign']}: {e}")
        else:
            # For standard mode, create zones based on capacity
            channel_chunks = [filtered_list[i:i + args.zone_capacity] for i in range(0, len(filtered_list), args.zone_capacity)]
            
            for chunk_num, chunk in enumerate(channel_chunks, 1):
                if len(channel_chunks) == 1:
                    zone_name = args.name
                else:
                    zone_name = f'{args.name} #{chunk_num}'
                
                # Collect channel names and frequencies
                channel_names = []
                rx_freqs = []
                tx_freqs = []
                
                for item in chunk:
                    # Create city abbreviation
                    city = item['city'].split(',')[0].strip()
                    city_abbr = city[:3].upper() if len(city) >= 3 else (city + 'XXX')[:3].upper()
                    
                    # Create channels for both timeslots with same logic as channels.csv
                    for slot in [1, 2]:
                        base_name = f"{item['callsign']}.{city_abbr}"
                        ts_suffix = f" TS{slot}"
                        if len(base_name + ts_suffix) > 16:
                            max_callsign_len = 16 - len(f".{city_abbr}{ts_suffix}")
                            truncated_callsign = item['callsign'][:max_callsign_len]
                            ch_alias = f"{truncated_callsign}.{city_abbr}{ts_suffix}"
                        else:
                            ch_alias = base_name + ts_suffix
                        
                        channel_names.append(ch_alias)
                        rx_freqs.append(item['tx'])
                        tx_freqs.append(item['rx'])
                
                # Write zone row with Zone Hide column
                writer.writerow([chunk_num, zone_name, '|'.join(channel_names), '|'.join(rx_freqs), 
                               '|'.join(tx_freqs), channel_names[0] if channel_names else '', 
                               rx_freqs[0] if rx_freqs else '', tx_freqs[0] if tx_freqs else '',
                               channel_names[0] if channel_names else '', 
                               rx_freqs[0] if rx_freqs else '', tx_freqs[0] if tx_freqs else '', '0'])
    
    print(f'Zones CSV file "{zones_file}" written.')


def write_talkgroups_csv():
    """Write talkgroups data to talkgroups.csv (already in correct format)"""
    import os
    
    talkgroups_file = os.path.join(args.output, 'talkgroups.csv')
    
    if os.path.exists(talkgroups_file):
        print(f'Talkgroups CSV file "{talkgroups_file}" already exists with user template data.')
    else:
        print('No talkgroups.csv found')


if __name__ == '__main__':
    download_file()
    filter_list()
    process_channels()
    
    # Write CSV files
    write_channels_csv()
    if args.talkgroups:
        write_talkgroups_csv()
    write_zones_csv()
    
    cleanup_contact_uploads()