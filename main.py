#!/usr/bin/env python3
"""SBD Visualization - Real-time slot-based driving visualization.

Connects to slot_controller via TCP to receive state updates and displays:
- Robot positions with heading arrows
- Slot grid with occupancy status
- Target slot indicators
"""

import json
import math
import socket
import sys
import threading
import time

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

# Connection settings
SLOT_CONTROLLER_HOST = "localhost"
SLOT_CONTROLLER_PORT = 5006

# Thread-safe shared state (avoids Streamlit session_state warnings)
@st.cache_resource
def get_shared_state():
    return {
        'vis_state': {'slots': [], 'robots': []},
        'connected': False,
        'last_update': 0,
        'lock': threading.Lock()
    }

# Road dimensions (from params.yaml)
AREA_WIDTH = 1.8  # road_length
AREA_HEIGHT = 1.8  # 6 lanes * 0.3m lane_width
LANE_WIDTH = 0.3

# Visualization settings
FIG_SIZE = (12, 4)
ROBOT_RADIUS = 0.05
SLOT_WIDTH = 0.1  # slot_length
SLOT_HEIGHT = 0.15
VIEW_MARGIN = 0.2


def socket_receiver_thread():
    """Background thread that connects to slot_controller and receives state updates."""
    shared = get_shared_state()
    buffer = ""

    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            print(f"[VIS] Connecting to {SLOT_CONTROLLER_HOST}:{SLOT_CONTROLLER_PORT}...")
            sock.connect((SLOT_CONTROLLER_HOST, SLOT_CONTROLLER_PORT))
            print("[VIS] Connected successfully!")

            with shared['lock']:
                shared['connected'] = True
            sock.settimeout(30.0)  # 30 second timeout for receiving data

            while True:
                try:
                    data = sock.recv(4096)
                    if not data:
                        print("[VIS] Connection closed by server (empty data)")
                        break

                    buffer += data.decode('utf-8')

                    # Process complete JSON messages (newline-delimited)
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        if line.strip():
                            clean_line = line.replace("[VIS BROADCAST] Data: ", "").strip()
                            print(f"[VIS] Received raw data ({len(line)} bytes): {clean_line[:200]}...")  # Print first 200 chars
                            try:
                                state = json.loads(clean_line)
                                print(f"[VIS] Parsed state: {len(state.get('slots', []))} slots, {len(state.get('robots', []))} robots")
                                with shared['lock']:
                                    shared['vis_state'] = state
                                    shared['last_update'] = time.time()
                            except json.JSONDecodeError as e:
                                print(f"[VIS] JSON decode error: {e}")
                                print(f"[VIS] Bad data: {line}")

                except socket.timeout:
                    print("[VIS] Receive timeout - no data for 30s")
                    break

        except ConnectionRefusedError:
            print("[VIS] Connection refused - is slot_controller running?")
        except socket.timeout:
            print("[VIS] Connection timeout")
        except (socket.error, OSError) as e:
            print(f"[VIS] Socket error: {e}")
        except Exception as e:
            print(f"[VIS] Unexpected error: {type(e).__name__}: {e}")
        finally:
            with shared['lock']:
                shared['connected'] = False
            try:
                sock.close()
            except:
                pass

        # Wait before reconnecting
        print("[VIS] Reconnecting in 2 seconds...")
        time.sleep(2.0)


def draw_visualization(state: dict) -> None:
    """Draw the road, slots, and robots."""
    fig, ax = plt.subplots(figsize=FIG_SIZE, facecolor=(0.1, 0.1, 0.1))

    # Set up axes
    xmin = -VIEW_MARGIN
    xmax = AREA_WIDTH + VIEW_MARGIN
    ymin = -VIEW_MARGIN
    ymax = AREA_HEIGHT + VIEW_MARGIN

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect('equal')
    ax.set_facecolor((0.15, 0.15, 0.15))

    # Draw road surface
    road = patches.Rectangle(
        (0, 0), AREA_WIDTH, AREA_HEIGHT,
        facecolor=(0.3, 0.3, 0.3),
        edgecolor=(0.5, 0.5, 0.5),
        linewidth=2
    )
    ax.add_patch(road)

    # Draw lane dividers (5 dividers for 6 lanes)
    for lane_idx in range(1, 6):  # Dividers at y = 0.3, 0.6, 0.9, 1.2, 1.5
        lane_y = lane_idx * LANE_WIDTH
        ax.axhline(lane_y, color='white', linewidth=1.5, linestyle='--', alpha=0.7)

    # Draw slots
    slots = state.get('slots', [])
    for slot in slots:
        slot_x = slot['x']
        slot_y = slot['y']

        # Determine slot color based on status
        if slot.get('filled', False):
            color = '#ff4444'  # Red - occupied
            edge_color = '#ff0000'
        elif slot.get('reserved', False):
            color = '#ffaa00'  # Yellow - reserved
            edge_color = '#ff8800'
        else:
            color = '#44ff44'  # Green - empty
            edge_color = '#00ff00'

        # Draw slot rectangle centered at slot position
        slot_rect = patches.Rectangle(
            (slot_x - SLOT_WIDTH / 2, slot_y - SLOT_HEIGHT / 2),
            SLOT_WIDTH, SLOT_HEIGHT,
            facecolor=color,
            edgecolor=edge_color,
            linewidth=2,
            alpha=0.5
        )
        ax.add_patch(slot_rect)

        # Draw slot ID
        ax.text(slot_x, slot_y, str(slot['id']),
                ha='center', va='center',
                fontsize=8, color='white', fontweight='bold')

    # Draw robots
    robots = state.get('robots', [])
    robot_colors = {'db7': '#00aaff', 'db9': '#ff5500'}

    for robot in robots:
        name = robot['name']
        x = robot['x']
        y = robot['y']
        theta = robot.get('theta', 0)

        color = robot_colors.get(name, '#ffffff')

        # Draw robot circle
        robot_circle = patches.Circle(
            (x, y), ROBOT_RADIUS,
            facecolor=color,
            edgecolor='white',
            linewidth=2
        )
        ax.add_patch(robot_circle)

        # Draw heading arrow 
        # not sure if there is issue with recieved data or visualisation, 
        # but adding 90 degrees to makes heading visualisation correct)
        visual_theta = theta + (math.pi / 2)
        arrow_length = ROBOT_RADIUS * 1.5
        dx = arrow_length * math.cos(visual_theta)
        dy = arrow_length * math.sin(visual_theta)
        ax.arrow(x, y, dx, dy,
                 head_width=0.02, head_length=0.015,
                 fc='white', ec='white', linewidth=1.5)

        # Draw robot name
        ax.text(x, y + ROBOT_RADIUS + 0.03, name,
                ha='center', va='bottom',
                fontsize=9, color='white', fontweight='bold')

        # Draw dashed line to target slot
        target_slot_id = robot.get('target_slot_id')
        if target_slot_id is not None:
            for slot in slots:
                if slot['id'] == target_slot_id:
                    ax.plot([x, slot['x']], [y, slot['y']],
                            color=color, linestyle='--', linewidth=1.5, alpha=0.6)
                    break

    # Configure axes
    ax.set_xlabel('X (m)', color='white')
    ax.set_ylabel('Y (m)', color='white')
    ax.tick_params(colors='white')
    for spine in ax.spines.values():
        spine.set_color('white')

    st.pyplot(fig)
    plt.close(fig)


def main() -> None:
    st.set_page_config(page_title="SBD Visualization", layout="wide")
    st.title("Slot-Based Driving Visualization")

    # Initialize receiver thread (only once per process)
    if 'receiver_v2' not in st.session_state:
        st.session_state.receiver_v2 = False

    # Start receiver thread
    if not st.session_state.receiver_v2:
        thread = threading.Thread(target=socket_receiver_thread, daemon=True)
        thread.start()
        st.session_state.receiver_v2 = True

    # Get current state from thread-safe shared state
    shared = get_shared_state()
    with shared['lock']:
        state = shared['vis_state'].copy()
        connected = shared['connected']
        last_update = shared['last_update']

    # Layout
    col_left, col_mid = st.columns([1, 3])

    with col_left:
        # Connection status
        st.subheader("Connection")
        if connected:
            st.success("Connected to slot_controller")
        else:
            st.error("Disconnected - Reconnecting...")

        # Last update time
        if last_update > 0:
            elapsed = time.time() - last_update
            st.text(f"Last update: {elapsed:.1f}s ago")

        st.markdown("---")

        # Slot info
        st.subheader("Slots")
        slots = state.get('slots', [])

        if slots:
            for slot in sorted(slots, key=lambda s: s['id']):
                status = "Empty"
                if slot.get('filled'):
                    status = "Occupied"
                elif slot.get('reserved'):
                    status = "Reserved"
                st.text(f"Slot {slot['id']} (Lane {slot['lane']}): {status}")
        else:
            st.text("No slots")

        st.markdown("---")

        # Robot info
        st.subheader("Robots")
        robots = state.get('robots', [])

        if robots:
            for robot in robots:
                name = robot['name']
                x = robot.get('x', 0)
                y = robot.get('y', 0)
                theta = robot.get('theta', 0)
                velocity = robot.get('velocity', 0)
                target = robot.get('target_slot_id', 'None')
                in_slot = "Yes" if robot.get('in_slot') else "No"

                st.text(f"{name}:")
                st.text(f"  Pos: ({x:.3f}, {y:.3f})")
                st.text(f"  Theta: {theta:.3f} rad")
                st.text(f"  Velocity: {velocity:.4f} m/s")
                st.text(f"  Target: Slot {target}")
                st.text(f"  In slot: {in_slot}")
                st.text("")
        else:
            st.text("No robots detected")

    with col_mid:
        st.subheader("Road View")
        draw_visualization(state)

        # Legend
        legend_cols = st.columns(4)
        with legend_cols[0]:
            st.markdown(":green_circle: Empty slot")
        with legend_cols[1]:
            st.markdown(":yellow_circle: Reserved slot")
        with legend_cols[2]:
            st.markdown(":red_circle: Occupied slot")
        with legend_cols[3]:
            st.markdown("-- Target line")

    # Auto-refresh
    time.sleep(0.5)
    st.rerun()


if __name__ == "__main__":
    if get_script_run_ctx() is None:
        print("Run with: streamlit run main.py")
        sys.exit(0)
    main()
