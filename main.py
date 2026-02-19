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
import matplotlib.transforms as mtransforms
import numpy as np
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

# Connection settings
SLOT_CONTROLLER_HOST = "localhost"
SLOT_CONTROLLER_PORT = 5006

# Thread-safe shared state (avoids Streamlit session_state warnings)
@st.cache_resource
def get_shared_state():
    # Using a global dictionary to store state across reruns
    return {
        'vis_state': {'slots': [], 'robots': []},
        'connected': False,
        'last_update': 0,
        'lock': threading.Lock(),
        'thread_running': False 
    }




# Road dimensions (from params.yaml)
AREA_WIDTH = 2.6     # X-axis: slot travel direction (0→2.6)
AREA_HEIGHT = 1.9    # Y-axis: lanes stacked across (6 × 0.317m ≈ 1.9m)
LANE_WIDTH = 0.317

# Visualization settings
FIG_SIZE = (12, 8)   # Landscape orientation
ROBOT_RADIUS = 0.05
SLOT_WIDTH = 0.1     # Along-track width (X, = slot_length)
SLOT_HEIGHT = 0.15   # Cross-track height (Y)
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

    track_type = state.get('track_type', 'linear')

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

    if track_type == 'oval':
        # Draw oval track outline
        track_info = state.get('track', {})
        cx = track_info.get('center_x', 1.3)
        cy = track_info.get('center_y', 0.95)
        a = track_info.get('semi_major', 1.0)
        b = track_info.get('semi_minor', 0.65)

        oval = patches.Ellipse(
            (cx, cy), width=2 * a, height=2 * b,
            facecolor='none',
            edgecolor='white',
            linewidth=2,
            linestyle='--',
            alpha=0.7
        )
        ax.add_patch(oval)
    else:
        # Draw lane dividers (5 dividers for 6 horizontal lanes)
        for lane_idx in range(1, 6):  # Dividers at y = 0.317, 0.634, ...
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

        heading = slot.get('heading')

        if heading is not None:
            # Oval mode: draw rotated rectangle aligned to track tangent
            angle_deg = math.degrees(heading)
            slot_rect = patches.FancyBboxPatch(
                (-SLOT_WIDTH / 2, -SLOT_HEIGHT / 2),
                SLOT_WIDTH, SLOT_HEIGHT,
                boxstyle="round,pad=0.01",
                facecolor=color,
                edgecolor=edge_color,
                linewidth=2,
                alpha=0.5
            )
            # Build rotation + translation transform
            t = mtransforms.Affine2D().rotate(heading).translate(slot_x, slot_y) + ax.transData
            slot_rect.set_transform(t)
            ax.add_patch(slot_rect)
        else:
            # Linear mode: axis-aligned rectangle
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

        # Convert compass radians (0=North/+Y, clockwise) to math radians (0=East/+X, counter-clockwise)
        visual_theta = (math.pi / 2) - theta
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

    # Initialize receiver thread (ensure only one exists globally)
    if 'receiver_thread_started' not in st.session_state:
        # Check if we already have a running thread in the global resource cache
        # We can attach a flag to the shared state to track if the thread is running
        shared_state = get_shared_state()
        
        # We use a purely local check here to avoid re-spawning 
        # But to be truly safe across sessions, we should check a global flag
        # embedded in the shared state object itself
        if not shared_state.get('thread_running', False):
             with shared_state['lock']:
                if not shared_state.get('thread_running', False):
                    thread = threading.Thread(target=socket_receiver_thread, daemon=True)
                    thread.start()
                    shared_state['thread_running'] = True
                    print("[VIS] Started background receiver thread")
        
        st.session_state.receiver_thread_started = True

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
        track_type = state.get('track_type', 'linear')
        st.subheader("Slots")
        slots = state.get('slots', [])

        if track_type == 'oval':
            st.text("Track: Oval")
            track_info = state.get('track', {})
            st.text(f"  Speed: {track_info.get('semi_major', 0):.2f} x {track_info.get('semi_minor', 0):.2f}m")

        if slots:
            for slot in sorted(slots, key=lambda s: s['id']):
                status = "Empty"
                if slot.get('filled'):
                    status = "Occupied"
                elif slot.get('reserved'):
                    status = "Reserved"
                if track_type == 'oval':
                    st.text(f"Slot {slot['id']} (Track): {status}")
                else:
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

    # Auto-refresh via Streamlit fragment or simply relying on interactions.
    # Using st.rerun() in a loop at the end of the script prevents the script 
    # from ever "finishing", confusing the frontend into thinking it's still loading.
    # Instead, we can use st.empty() for the dynamic parts or stream via a generator,
    # but the simplest fix for "loading forever" with st.rerun() is to ensure 
    # we don't hog the thread entirely or use a key to trigger updates.
    
    # However, for a real-time dashboard, we want the loop.
    # The "loading" indicator is because the script re-runs immediately.
    # A slightly better approach is using `st.empty` containers in a loop for the *data* 
    # rather than rerunning the whole page, but that breaks Streamlit's execution model slightly.
    
    # Let's try to increase the sleep time slightly to see if it helps, 
    # or better, use st.empty() logic if we can refactor.
    # Refactoring to a while loop inside main with st.empty() is safer.
    
    # Current quick fix: Just sleep longer? No, that just slows updates.
    # The actual fix: Streamlit 1.37+ introduced fragment. But without that, 
    # we should check if we can avoid the full rerun.
    
    # For now, let's keep st.rerun() but handle the "loading" spinner gracefully.
    # Actually, the user says "stays loading indefinitely", which might mean it never renders the FIRST frame.
    
    time.sleep(0.5) 
    st.rerun()


if __name__ == "__main__":
    if get_script_run_ctx() is None:
        
        
        print("Run with: streamlit run main.py")
        sys.exit(0)
    main()
