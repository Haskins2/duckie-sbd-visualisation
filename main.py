import sys
import pygame


WINDOW_WIDTH = 900
WINDOW_HEIGHT = 900
AREA_METERS = 1.58
GRID_SPACING_METERS = 0.10
SLOT_WIDTH_METERS = 0.12
SLOT_HEIGHT_METERS = 0.08
ROBOT_RADIUS_METERS = 0.03
ROBOT_STEP_METERS = 0.02
PADDING_PIXELS = 60


class FieldView:
	def __init__(self, surface: pygame.Surface):
		self.surface = surface
		self.scale = min(
			(WINDOW_WIDTH - 2 * PADDING_PIXELS) / AREA_METERS,
			(WINDOW_HEIGHT - 2 * PADDING_PIXELS) / AREA_METERS,
		)
		self.area_pixels = AREA_METERS * self.scale
		self.top_left = (
			(WINDOW_WIDTH - self.area_pixels) / 2,
			(WINDOW_HEIGHT - self.area_pixels) / 2,
		)

	def world_to_screen(self, x: float, y: float) -> tuple[int, int]:
		sx = self.top_left[0] + x * self.scale
		sy = self.top_left[1] + self.area_pixels - y * self.scale
		return int(sx), int(sy)

	def draw_background(self) -> None:
		self.surface.fill((18, 18, 18))
		rect = pygame.Rect(
			self.top_left[0],
			self.top_left[1],
			self.area_pixels,
			self.area_pixels,
		)
		pygame.draw.rect(self.surface, (40, 40, 40), rect)

	def draw_grid(self) -> None:
		lines = int(AREA_METERS / GRID_SPACING_METERS) + 1
		for i in range(lines + 1):
			x_m = min(i * GRID_SPACING_METERS, AREA_METERS)
			x_px = self.top_left[0] + x_m * self.scale
			pygame.draw.line(
				self.surface,
				(70, 70, 70),
				(x_px, self.top_left[1]),
				(x_px, self.top_left[1] + self.area_pixels),
				1,
			)
			y_m = min(i * GRID_SPACING_METERS, AREA_METERS)
			y_px = self.top_left[1] + y_m * self.scale
			pygame.draw.line(
				self.surface,
				(70, 70, 70),
				(self.top_left[0], y_px),
				(self.top_left[0] + self.area_pixels, y_px),
				1,
			)

	def draw_slot(self) -> None:
		slot_cx = AREA_METERS / 2
		slot_cy = AREA_METERS / 2
		slot_px_w = SLOT_WIDTH_METERS * self.scale
		slot_px_h = SLOT_HEIGHT_METERS * self.scale
		top_left_x = self.top_left[0] + (slot_cx - SLOT_WIDTH_METERS / 2) * self.scale
		top_left_y = self.top_left[1] + self.area_pixels - (slot_cy + SLOT_HEIGHT_METERS / 2) * self.scale
		rect = pygame.Rect(top_left_x, top_left_y, slot_px_w, slot_px_h)
		pygame.draw.rect(self.surface, (0, 170, 255), rect, width=3, border_radius=4)

	def draw_border(self) -> None:
		rect = pygame.Rect(
			self.top_left[0],
			self.top_left[1],
			self.area_pixels,
			self.area_pixels,
		)
		pygame.draw.rect(self.surface, (200, 200, 200), rect, width=3)

	def draw_robot(self, position: tuple[float, float]) -> None:
		sx, sy = self.world_to_screen(position[0], position[1])
		radius = int(ROBOT_RADIUS_METERS * self.scale)
		pygame.draw.circle(self.surface, (255, 80, 80), (sx, sy), radius)
		pygame.draw.circle(self.surface, (255, 255, 255), (sx, sy), max(1, radius // 3))


def clamp_position(pos: tuple[float, float]) -> tuple[float, float]:
	margin = ROBOT_RADIUS_METERS
	x = max(margin, min(AREA_METERS - margin, pos[0]))
	y = max(margin, min(AREA_METERS - margin, pos[1]))
	return x, y


def main() -> None:
	pygame.init()
	screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
	pygame.display.set_caption("Slot-based driving viewer")
	clock = pygame.time.Clock()
	font = pygame.font.SysFont("arial", 18)
	field = FieldView(screen)
	robot_pos = (AREA_METERS / 2, AREA_METERS / 2)

	running = True
	while running:
		clock.tick(60)
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				running = False

		keys = pygame.key.get_pressed()
		move_x = (keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]) * ROBOT_STEP_METERS
		move_y = (keys[pygame.K_UP] - keys[pygame.K_DOWN]) * ROBOT_STEP_METERS
		robot_pos = clamp_position((robot_pos[0] + move_x, robot_pos[1] + move_y))

		field.draw_background()
		field.draw_grid()
		field.draw_border()
		field.draw_slot()
		field.draw_robot(robot_pos)

		pos_text = font.render(f"Robot: {robot_pos[0]:.2f} m, {robot_pos[1]:.2f} m", True, (230, 230, 230))
		screen.blit(pos_text, (20, 20))
		slot_text = font.render("Slot: 0.12m x 0.08m centered", True, (180, 220, 255))
		screen.blit(slot_text, (20, 45))

		pygame.display.flip()

	pygame.quit()
	sys.exit()


if __name__ == "__main__":
	main()
