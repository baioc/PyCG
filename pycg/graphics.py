"""Computer Graphics API."""

from math import pi, sqrt, cos, sin, inf
from typing import Iterable, Tuple, Sequence

from blas import Vector, Matrix
from utilities import pairwise, clamp


class Painter():
    """Interface providing primitive graphics drawing."""

    def draw_pixel(self, x: int, y: int):
        raise NotImplementedError("Painter is an abstract class.")

    def draw_line(self, xa: int, ya: int, xb: int, yb: int):
        # Bresenham's line algorithm, which is based on a decision parameter p
        # allowing to solve y = mx + c using only integer operations {+, -, 2*}
        xa, ya, xb, yb = int(xa), int(ya), int(xb), int(yb)  # coerce to int
        dx = xb - xa
        dy = yb - ya
        sign_x = +1 if dx >= 0 else -1
        sign_y = +1 if dy >= 0 else -1
        x, y = xa, ya

        # common subexpression optimization
        DX2 = 2*dx*sign_x
        DY2 = 2*dy*sign_y
        DY2X2 = DY2 - DX2
        DX2Y2 = DX2 - DY2

        if abs(dx) >= abs(dy):
            # pi = (d1-d2)*dx, d1 = y - yi, d2 = (yi + 1) - y => p = 2*dy - dx
            p = 2*dy*sign_y - dx*sign_x

            # dp = 2*dy - 2*dx*inc_x
            for _ in range(dx*sign_x + 1):
                self.draw_pixel(x, y)
                x += sign_x
                if p >= 0:
                    y += sign_y
                    p += DY2X2
                else:
                    p += DY2
        else:
            # pi = (d1-d2)*dy, d1 = x - xi, d2 = (xi + 1) - x => p = 2*dx - dy
            p = 2*dx*sign_x - dy*sign_y

            # dp = 2*dx - 2*dy*inc_y
            for _ in range(dy*sign_y + 1):
                self.draw_pixel(x, y)
                y += sign_y
                if p >= 0:
                    x += sign_x
                    p += DX2Y2
                else:
                    p += DX2

    def draw_polygon(self, points: Sequence[Tuple[int, int]]):
        raise NotImplementedError("Painter is an abstract class.")


class Transformation:
    """Representation of Transformations in 3D Homogeneous Coordinates.

    Methods such as `translate`, `rotate` and `scale` modify the calling object
    and return it afterwards, allowing for chaining. eg:

        t = Transformation().translate(tx, ty, tz).rotate(theta).scale(s)

    These operations are all applied at the same time.
    """

    def __init__(self):
        self.translation = Vector(0, 0, 0)
        self.rotation = 0
        self.scaling = Vector(1, 1, 1)

    def is_identity(self) -> bool:
        return (self.translation.length == 0
                and self.rotation == 0
                and self.scaling == Vector(1, 1, 1))

    def translate(self, tx: float, ty: float, tz: float = 0):
        self.translation += (tx, ty, tz)
        return self

    def rotate(self, theta):
        self.rotation += theta
        return self

    def scale(self, scale: float, sy: float = None, sz: float = None, sx: float = None):
        # scale all axis the same when given a single factor
        if not sx and not sy and not sz:
            sx = scale
            sy = scale
            sz = scale
        # otherwise, assume the first factor is for sx and use 1 as default
        else:
            sx = scale
            sy = sy or 1
            sz = sz or 1
        self.scaling.x *= sx
        self.scaling.y *= sy
        self.scaling.z *= sz
        return self

    @staticmethod
    def _scaling(scales: Sequence[float]) -> Matrix:
        t = Matrix.identity(4)
        for i in range(t.rows - 1):
            t[i][i] = scales[i]  # modify each diagonal to the scaling
        return t

    @staticmethod
    def _translation(deltas: Sequence[float]) -> Matrix:
        t = Matrix.identity(4)
        for i in range(t.rows - 1):
            t[i][-1] = deltas[i]  # apply delta to last column of each row
        return t

    @staticmethod
    def _rotation_x(theta: float) -> Matrix:
        cs, sn = cos(theta), sin(theta)
        roll = Matrix([1, 0,  0,   0],
                      [0, cs, -sn, 0],
                      [0, sn, cs,  0],
                      [0, 0,  0,   1])
        return roll

    @staticmethod
    def _rotation_y(theta: float) -> Matrix:
        cs, sn = cos(theta), sin(theta)
        pitch = Matrix([cs,  0, sn, 0],
                       [0,   1, 0,  0],
                       [-sn, 0, cs, 0],
                       [0,   0, 0,  1])
        return pitch

    @staticmethod
    def _rotation_z(theta: float) -> Matrix:
        cs, sn = cos(theta), sin(theta)
        yaw = Matrix([cs, -sn, 0, 0],
                     [sn, cs,  0, 0],
                     [0,   0,  1, 0],
                     [0,   0,  0, 1])
        return yaw

    @staticmethod
    def _rotate_2D(vec: Vector, theta: float) -> Vector:
        x, y = vec.x, vec.y
        cs, sn = cos(theta), sin(theta)
        return Vector(x*cs - y*sn, x*sn + y*cs)

    def matrix(self, pivot = None, axis: Vector = None) -> Matrix:
        """Gets the 4x4 Matrix that performs this transformation on vectors.
        Pivot defaults to global origin and axis to the global Z axis.
        """
        if self.is_identity(): return Matrix.identity(4)

        # notice the axis is always a new variable -> ok to mutate
        pivot = pivot or Point(0, 0, 0)
        axis = axis.normalized() if axis else Vector(0, 0, 1)

        # we need to translate pivot to origin for scaling and rotation
        to_origin = Transformation._translation(-pivot)
        back_from_origin = Transformation._translation(pivot)
        scale = Transformation._scaling(self.scaling)

        # align object axis to the XY plane by rotating along X
        projectiony_yz = Vector(axis.y, axis.z)
        align_xy_angle = -Vector.angle(projectiony_yz, Vector(1, 0))
        aligned = Transformation._rotate_2D(projectiony_yz, align_xy_angle)
        align_xy = Transformation._rotation_x(align_xy_angle)
        unalign_xy = Transformation._rotation_x(-align_xy_angle)

        # align new object axis with the Y axis by rotating along Z
        projection_xy = Vector(axis.x, aligned[0])
        align_y_angle = -Vector.angle(projection_xy, Vector(0, 1))
        align_y = Transformation._rotation_z(align_y_angle)
        unalign_y = Transformation._rotation_z(-align_y_angle)

        # then, we rotate along Y by the angle we actually wanted
        rotate_aligned = Transformation._rotation_y(self.rotation)

        # translation is easy
        translate = Transformation._translation(self.translation)

        # this should be read bottom-up:
        return (back_from_origin
                @ translate
                @ unalign_xy
                @ unalign_y
                @ rotate_aligned
                @ align_y
                @ align_xy
                @ scale
                @ to_origin)


class Drawable():
    """Common interface for all graphical objects."""

    def _error(self):
        raise NotImplementedError("Drawable is an abstract class.")

    def draw(self, painter: Painter):
        self._error()

    def transform(self, transformation: Matrix):
        self._error()

    def center(self):  # -> Point:
        self._error()


class Point(Drawable, Vector):
    def __init__(self, x, y, z=1, _=1):
        Vector.__init__(self, x, y, z, 1)

    def __repr__(self):  # as by the Well-known text representation of geometry
        return f"POINT ({self.x} {self.y} {self.z})"

    def __eq__(self, other):
        if len(other) < 2: return False
        for a, b in zip(self, other):
            if a != b:
                return False
        return True

    def draw(self, painter):  # TODO: projection
        painter.draw_pixel(self.x, self.y)

    def transform(self, transformation: Matrix):
        self.x, self.y, self.z, _ = Point(*(transformation @ self))

    def center(self):  # -> Point:
        return self


class Line(Drawable):
    def __init__(self, pa: Point, pb: Point):
        self._points = [pa, pb]

    def __len__(self) -> int:
        return 2

    def __getitem__(self, key: int) -> Point:
        return self._points[key]

    def __setitem__(self, key: int, point: Point):
        self._points[key] = point

    def __repr__(self):  # WKT
        return f"LINESTRING ({self[0].x} {self[0].y} {self[0].z}, {self[1].x} {self[1].y}, {self[0].z})"

    def __eq__(self, other: Sequence[Point]) -> bool:
        if len(other) != len(self): return False
        for p1, p2 in zip(self, other):
            if p1 != p2:
                return False
        return True

    def draw(self, painter):  # TODO: projection
        painter.draw_line(self[0].x, self[0].y, self[1].x, self[1].y)

    def transform(self, transformation: Matrix):
        for i, point in enumerate(self._points):
            self._points[i] = Point(*(transformation @ point))

    def center(self) -> Point:
        return (self[0] + self[1]) / 2

    @property
    def length(self) -> float:
        return sqrt((self[0].x - self[1].x)**2 + (self[0].y - self[1].y)**2 + (self[0].z - self[1].z)**2)


class Wireframe(Drawable):
    """Open polygon defined by a sequence of connected points."""

    def __init__(self, points: Sequence[Point]):
        self._points = points

    def __len__(self):
        return len(self._points)

    def __getitem__(self, key: int) -> Point:
        return self._points[key]

    def __setitem__(self, key: int, point: Point):
        self._points[key] = point

    def __repr__(self):  # WKT
        points = ', '.join(f'{p.x} {p.y} {p.z}' for p in self._points)
        return f"LINESTRING ({points})"

    def __eq__(self, other: Iterable) -> bool:
        if len(other) != len(self): return False
        for p1, p2 in zip(self, other):
            if p1 != p2:
                return False
        return True

    def draw(self, painter):  # TODO: projection
        for pa, pb in pairwise(self._points):
            painter.draw_line(pa.x, pa.y, pb.x, pb.y)

    def transform(self, transformation: Matrix):
        for i, point in enumerate(self._points):
            self._points[i] = Point(*(transformation @ point))

    def center(self) -> Point:
        # to avoid overweighting repeated points, only average over unique ones
        points = set({tuple(p) for p in self._points})
        average = Point(0, 0, 0)
        for p in points:
            average += p
        return average / len(points)


class Polygon(Wireframe):
    """Filled polygon."""

    def __init__(self, points: Sequence[Point]):
        points = list(points)
        if points[-1] != points[0]:  # ensures polygons are closed
            p = points[0]
            points.append(Point(p.x, p.y, p.z))
        super().__init__(points)

    def __repr__(self):  # WKT
        points = ', '.join(f'{p.x} {p.y} {p.z}' for p in self._points)
        return f"POLYGON (({points}))"

    def draw(self, painter):  # TODO: projection
        painter.draw_polygon([(p.x, p.y) for p in self._points])


class Bezier(Wireframe):
    def __init__(self, points: Sequence[Point], step=0.01):
        super().__init__(bezier(points, step))

# TODO: 3D curves?

class BSpline(Wireframe):
    def __init__(self, points: Sequence[Point], step=0.01):
        super().__init__(bSpline(points, step))


class Camera(Painter):
    """Window used as reference to render objects."""

    def __init__(self, painter: Painter, size: Vector, offset: Point = None):
        self.painter = painter
        self._viewport_size = size
        self._offset = offset or Point(0, 0)
        self._position = Point(0, 0)
        self._zoom = 1.0
        self._angle = 0
        self._dirty = True
        self._world_to_view = None
        self._view_to_screen = None
        self.line_clipping_algorithm = 'Liang-Barsky'

    def draw_pixel(self, x, y):
        self._recompute_matrixes()
        p = self._world_to_view @ Point(x, y)
        if -1 <= p.x <= 1 and -1 <= p.y <= 1:
            p = self._view_to_screen @ p
            self.painter.draw_pixel(int(p.x), int(p.y))

    def draw_line(self, xa, ya, xb, yb):
        self._recompute_matrixes()
        a = self._world_to_view @ Point(xa, ya)
        b = self._world_to_view @ Point(xb, yb)
        clipper = (make_clipper(-1, +1, -1, +1)
                   if self.line_clipping_algorithm == 'Cohen-Sutherland'
                   else clip_line)
        clipped = clipper(a.x, a.y, b.x, b.y)
        if clipped:
            xa, ya, xb, yb = clipped
            a = self._view_to_screen @ Point(xa, ya)
            b = self._view_to_screen @ Point(xb, yb)
            self.painter.draw_line(int(a.x), int(a.y), int(b.x), int(b.y))

    def draw_polygon(self, points: Sequence[Tuple[int, int]]):
        self._recompute_matrixes()

        clipspace = []
        for x, y in points:
            x, y, *_ = self._world_to_view @ Point(x, y)
            clipspace.append((x, y))

        clipped = clip_polygon(clipspace)

        screenspace = []
        for x, y in clipped:
            x, y, *_ = self._view_to_screen @ Point(x, y)
            screenspace.append((int(x), int(y)))

        if screenspace: self.painter.draw_polygon(screenspace)

    def _recompute_matrixes(self):
        # only actually recompute if the camera has changed
        if self._dirty:
            half_size = self._viewport_size / 2

            center = Transformation().translate(-self.x, -self.y).matrix()
            align = Transformation().rotate(-self.angle).matrix()
            scaling = half_size / self.zoom
            normalize = Transformation().scale(1/scaling.x, 1/scaling.y).matrix()
            self._world_to_view = normalize @ align @ center

            resize = Transformation().scale(half_size.x, half_size.y).matrix()
            corner = Transformation().translate(half_size.x, -half_size.y).matrix()
            invert_y = Transformation().scale(1, -1).matrix()
            offset = Transformation().translate(self._offset.x, self._offset.y).matrix()
            self._view_to_screen = offset @ invert_y @ corner @ resize

            self._dirty = False

    @property
    def x(self):
        return self._position.x

    @x.setter
    def x(self, x):
        self._position.x = x
        self._dirty = True

    @property
    def y(self):
        return self._position.y

    @y.setter
    def y(self, y):
        self._position.y = y
        self._dirty = True

    @property
    def zoom(self) -> float:
        return self._zoom

    @zoom.setter
    def zoom(self, scale: float):
        if scale <= 0:
            raise ValueError("Camera zoom should be strictly positive.")
        self._zoom = scale
        self._dirty = True

    @property
    def angle(self) -> float:
        return self._angle

    @angle.setter
    def angle(self, theta: float):
        self._angle = theta
        self._dirty = True

    @property
    def viewport_size(self) -> Vector:
        return self._viewport_size

    @viewport_size.setter
    def viewport_size(self, size: Tuple[int, int]):
        w, h = size
        self._viewport_size = Vector(w, h)
        self._dirty = True


class Color:
    def __init__(self, r, g, b, a = 0xFF):
        self._r = clamp(int(r), 0x00, 0xFF)
        self._g = clamp(int(g), 0x00, 0xFF)
        self._b = clamp(int(b), 0x00, 0xFF)
        self._a = clamp(int(a), 0x00, 0xFF)

    def __repr__(self):
        return '#' + ''.join('%02x' % x for x in (self.r, self.g, self.b))

    def __eq__(self, other) -> bool:
        return self.r == other.r \
           and self.g == other.g \
           and self.b == other.b \
           and self.a == other.a

    @property
    def r(self):
        return self._r

    @r.setter
    def r(self, r):
        self._r = clamp(int(r), 0x00, 0xFF)

    @property
    def g(self):
        return self._g

    @g.setter
    def g(self, g):
        self._g = clamp(int(g), 0x00, 0xFF)

    @property
    def b(self):
        return self._b

    @b.setter
    def b(self, b):
        self._b = clamp(int(b), 0x00, 0xFF)

    @property
    def a(self):
        return self._a


def clip_line(xa: float, ya: float, xb: float, yb: float) -> Sequence[float]:
    """Straightforward Liang-Barsky normalized line clipping algorithm."""

    # we assume input coordinates are normalized
    x_min, x_max = (-1, 1)
    y_min, y_max = (-1, 1)

    # compute distance from window borders
    qs = (
        xa - x_min, # left
        x_max - xa, # right
        ya - y_min, # bottom
        y_max - ya, # up
    )

    # also the displacements
    dx = xb - xa
    dy = yb - ya
    ps = (-dx, dx, -dy, dy)

    # when any p == 0, the line is parallel to one side of the window, in
    # which case we can quickly tell whether the line is completely outside
    for p, q in zip(ps, qs):
        if p == 0 and q < 0:
            return []

    # for all other cases, we take an argument u in [0,1] and consider
    # x = xa + u*dx        and        y = yb + u*dy
    u1, u2 = 0, 1

    # update parameters
    for p, q in zip(ps, qs):
        if p < 0:    # out -> in
            u1 = max(u1, q / p)
        elif p > 0:  # in -> out
            u2 = min(u2, q / p)
    else:
        if u1 > u2:  # line completely outside
            return []

    # by default, assume no clipping
    x1, y1, x2, y2 = xa, ya, xb, yb

    # if zero we reject u1
    if u1 != 0:
        x1 = xa + u1*dx
        y1 = ya + u1*dy

    # if one we reject u2
    if u2 != 1:
        x2 = xa + u2*dx
        y2 = ya + u2*dy

    return [x1, y1, x2, y2]


def make_clipper(x_min: float, x_max: float, y_min: float, y_max: float):
    """Creates a line clipper that respects the given window bounds."""

    def _cohen_sutherland(xa: float, ya: float, xb: float, yb: float) -> Sequence[float]:
        # This method uses 4 bits and 9 quadrants to heuristically discover if
        # lines will cross the window or not
        #    1001 |  1000  | 1010
        #       __|________|__
        #         |        |
        #   0001  |  0000  | 0010
        #       __|________|__
        #         |        |
        #   0101  |  0100  | 0110
        left = 0b001
        right = 0b0010
        bottom = 0b100
        top = 0b1000
        inside = 0b000

        def calculate_rc(x: float, y: float):
            code = 0
            if x < x_min: code |= left
            if y < y_min: code |= bottom
            if x > x_max: code |= right
            if y > y_max: code |= top
            return code

        rcStart = calculate_rc(xa, ya)
        rcEnd   = calculate_rc(xb, yb)
        x1, y1, x2, y2 = xa, ya, xb, yb
        while True:
            if rcEnd == rcStart == inside:  # completely contained
                return [x1, y1, x2, y2]
            elif (rcStart & rcEnd) != 0:  # completely outside
                return []

            # could be visible. get at least one that is outside the window
            x, y = 0, 0
            outside_rc = rcEnd if rcEnd != inside else rcStart

            # used to calculate m and 1/m
            dy = yb - ya
            dx = xb - xa

            if outside_rc & left:
                x = x_min
                y = ya + dy/dx * (x_min - xa)
            elif outside_rc & right:
                x = x_max
                y = ya + dy/dx * (x_max - xa)
            elif outside_rc & bottom:
                y = y_min
                x = xa + dx/dy * (y_min - ya)
            elif outside_rc & top:
                y = y_max
                x = xa + dx/dy * (y_max - ya)

            if outside_rc == rcStart:
                x1, y1 = x, y
                rcStart = calculate_rc(x1, y1)
            else:
                x2, y2 = x, y
                rcEnd = calculate_rc(x2, y2)

    return _cohen_sutherland


def clip_polygon(points: Sequence[Tuple[float, float]]) -> Sequence[Tuple[float, float]]:
    """Sutherland polygon clipping algorithm over a normalized window."""

    # we assume input coordinates are normalized
    x_min, x_max = (-1, 1)
    y_min, y_max = (-1, 1)

    # Sutherland-Hodgman works well with Cohen-Sutherland
    clip_left = make_clipper(x_min, +inf, -inf, +inf)
    clip_up = make_clipper(-inf, +inf, -inf, y_max)
    clip_right = make_clipper(-inf, x_max, -inf, +inf)
    clip_down = make_clipper(-inf, +inf, y_min, +inf)

    for clip in (clip_left, clip_up, clip_right, clip_down):
        if not points: break
        new = []
        for a, b in pairwise(points):
            segment = clip(a[0], a[1], b[0], b[1])
            if not segment: continue
            xa, ya, xb, yb = segment
            new.append((xa, ya))
            if (xb, yb) != b: new.append((xb, yb))
        if new and new[-1] != new[0]: new.append(new[0])
        points = new

    return points


def bezier(points: Sequence[Point], step: float) -> Sequence[Point]:
    """Assumes number of points is of the form (4 + 3*i), iterates 4 by 4."""
    if len(points) < 3: return points
    if len(points) == 3: points = [points[0], points[1], points[1], points[2]]

    curve = []

    j = 0
    M = Matrix([-1, 3,  -3, 1],
               [3,  -6, 3,  0],
               [-3, 3,  0,  0],
               [1,  0,  0,  0])
    for i in range(0, len(points) - 3, 3):
        j = 0
        while j < 1:
            T = Matrix([j*j*j, j*j, j, 1])
            Gx = Vector(points[i].x, points[i+1].x, points[i+2].x, points[i+3].x)
            Gy = Vector(points[i].y, points[i+1].y, points[i+2].y, points[i+3].y)
            Gx = T @ M @ Gx
            Gy = T @ M @ Gy
            curve.append(Point(Gx[0], Gy[0]))
            j += step

    return curve

def bSpline(points: Sequence[Point], step: float) -> Sequence[Point]:
    if len(points) < 3: return points
    if len(points) == 3: points = [points[0], points[1], points[1], points[2]]

    curve = []

    d1 = step
    d2 = step*step
    d3 = step*step*step
    E = Matrix([0,    0,    0,  1],
               [d3,   d2,   d1, 0],
               [6*d3, 2*d2, 0,  0],
               [6*d3, 0,    0,  0])
    M = (1/6)*Matrix([-1, 3,  -3, 1],
                     [3,  -6, 3,  0],
                     [-3, 0,  3,  0],
                     [1,  4,  1,  0])
    ExM = E @ M
    for i in range(0, len(points) - 3):
        G = Vector(points[i], points[i+1], points[i+2], points[i+3])
        D = ExM @ G
        j = 0
        while True:
            j += step
            if j >= 1: break
            curve.append(Point(D[0][0], D[0][1]))
            D[0] += D[1]
            D[1] += D[2]
            D[2] += D[3]

    return curve
