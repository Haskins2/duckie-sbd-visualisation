import math
import sys
import json
import os
import time

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx


AREA_METERS = 1.58
GRID_SPACING_METERS = 0.10
SLOT_WIDTH_METERS = 0.12
SLOT_HEIGHT_METERS = 0.2
ROBOT_RADIUS_METERS = 0.03
ROBOT_STEP_METERS = 0.01
VIEW_MARGIN_METERS = 0.2
SLOT_STEP_METERS = 0.02

FIG_SIZE = (3, 3)


def clamp_position(pos: tuple[float, float]) -> tuple[float, float]:
	margin = ROBOT_RADIUS_METERS
	x = max(margin, min(AREA_METERS - margin, pos[0]))
	y = max(margin, min(AREA_METERS - margin, pos[1]))
	return x, y


def clamp_slot_center(pos: tuple[float, float]) -> tuple[float, float]:
	margin_x = SLOT_WIDTH_METERS / 2
	margin_y = SLOT_HEIGHT_METERS / 2
	x = max(margin_x, min(AREA_METERS - margin_x, pos[0]))
	y = max(margin_y, min(AREA_METERS - margin_y, pos[1]))
	return x, y


def move_slot(dx: float, dy: float) -> None:
	x, y = st.session_state.slot_center
	st.session_state.slot_center = clamp_slot_center((x + dx, y + dy))


def handle_key_input(key: str | None) -> None:
	return


def draw_field(robot_pos: tuple[float, float], slot_center: tuple[float, float]) -> None:
	fig, ax = plt.subplots(figsize=FIG_SIZE, facecolor=(0.05, 0.05, 0.05))
	xmin = -VIEW_MARGIN_METERS
	xmax = AREA_METERS + VIEW_MARGIN_METERS
	ymin = -VIEW_MARGIN_METERS
	ymax = AREA_METERS + VIEW_MARGIN_METERS
	ax.set_xlim(xmin, xmax)
	ax.set_ylim(ymin, ymax)
	ax.set_aspect("equal")
	ax.set_facecolor((0.10, 0.10, 0.10))
 
	# Grid lines
	grid_min = math.floor(xmin / GRID_SPACING_METERS) * GRID_SPACING_METERS
	grid_max = math.ceil(xmax / GRID_SPACING_METERS) * GRID_SPACING_METERS
	lines = int((grid_max - grid_min) / GRID_SPACING_METERS)
	for i in range(lines + 1):
		coord = grid_min + i * GRID_SPACING_METERS
		ax.axhline(coord, color="#444", linewidth=0.3)
		ax.axvline(coord, color="#444", linewidth=0.3)
  
  
	bounds = patches.Rectangle((0, 0), AREA_METERS, AREA_METERS, fill=False, edgecolor="#c8c8c8", linewidth=1.5)
	ax.add_patch(bounds)
	slot_origin = (slot_center[0] - SLOT_WIDTH_METERS / 2, slot_center[1] - SLOT_HEIGHT_METERS / 2)
	slot = patches.Rectangle(
		slot_origin,
		SLOT_WIDTH_METERS,
		SLOT_HEIGHT_METERS,
		fill=False,
		edgecolor="#00aaff",
		linewidth=2.5,
		linestyle="-",
		joinstyle="round",
	)
	ax.add_patch(slot)
	robot = patches.Circle(robot_pos, ROBOT_RADIUS_METERS, color="#ff5050")
	robot_center = patches.Circle(robot_pos, ROBOT_RADIUS_METERS / 3, color="#ffffff")
	ax.add_patch(robot)
	ax.add_patch(robot_center)
	ax.set_xticks([])
	ax.set_yticks([])
	for spine in ax.spines.values():
		spine.set_visible(False)
	st.pyplot(fig, width="content")
	plt.close(fig)


def load_robot_pos() -> tuple[float, float] | None:
	try:
		if os.path.exists("state.json"):
			with open("state.json", "r") as f:
				data = json.load(f)
				return float(data["x"]), float(data["y"])
	except Exception:
		pass
	return None


def main() -> None:
	st.set_page_config(page_title="SBD", layout="wide")
	st.title("Slot-based driving viewer")

	# Try to load robot position from file
	new_pos = load_robot_pos()
	if new_pos:
		st.session_state.robot_pos = new_pos

	if "robot_pos" not in st.session_state:
		st.session_state.robot_pos = (AREA_METERS / 2, AREA_METERS / 2)
	if "slot_center" not in st.session_state:
		st.session_state.slot_center = (AREA_METERS / 2, AREA_METERS / 2)
	col_left, col_mid, col_right = st.columns([1.0, 1.8, 1.1], gap="large")
	with col_left:
		st.subheader("Slot position")
		st.metric("X (m)", f"{st.session_state.slot_center[0]:.2f}")
		st.metric("Y (m)", f"{st.session_state.slot_center[1]:.2f}")
		st.markdown("---")
		st.subheader("Robot position")
		st.metric("X (m)", f"{st.session_state.robot_pos[0]:.2f}")
		st.metric("Y (m)", f"{st.session_state.robot_pos[1]:.2f}")
	with col_mid:
		st.subheader("Field view")
		draw_field(st.session_state.robot_pos, st.session_state.slot_center)
	with col_right:
		st.subheader("Controls")
		row_up = st.columns([1, 1, 1])
		with row_up[1]:
			if st.button("⬆️", use_container_width=True):
				move_slot(0, SLOT_STEP_METERS)
		row_mid = st.columns([1, 1, 1])
		with row_mid[0]:
			if st.button("⬅️", use_container_width=True):
				move_slot(-SLOT_STEP_METERS, 0)
		with row_mid[1]:
			if st.button("⏺️", use_container_width=True):
				st.session_state.slot_center = (AREA_METERS / 2, AREA_METERS / 2)
		with row_mid[2]:
			if st.button("➡️", use_container_width=True):
				move_slot(SLOT_STEP_METERS, 0)
		row_down = st.columns([1, 1, 1])
		with row_down[1]:
			if st.button("⬇️", use_container_width=True):
				move_slot(0, -SLOT_STEP_METERS)
		st.markdown("---")

		st.subheader("Robot info")
		st.text("Name: DuckieBot")
		st.text("Connection: Connected")

	time.sleep(0.1)
	st.rerun()


if __name__ == "__main__":
	if get_script_run_ctx() is None:
		print("Run with: streamlit run main.py")
		sys.exit(0)
	main()
