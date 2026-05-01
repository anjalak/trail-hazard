from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from urllib import error, request

try:
    import rclpy
    from geometry_msgs.msg import Pose, PoseArray, PoseStamped
    from nav_msgs.msg import Path
    from rclpy.node import Node
    from std_msgs.msg import Float32, Int32, String
except ImportError as exc:  # pragma: no cover - requires ROS runtime
    raise RuntimeError(
        "ROS dependencies are missing. Source your ROS 2 environment and install rclpy."
    ) from exc

from app.ros.bridge_payloads import bridge_status_from_payload, graphql_body_for_trail, route_points_from_payload


class TrailIntelBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("trailintel_bridge")
        self.declare_parameter("graphql_url", "http://localhost:8000/graphql")
        self.declare_parameter("trail_id", 1)
        self.declare_parameter("poll_seconds", 8.0)
        self.declare_parameter("frame_id", "map")

        self.graphql_url = self.get_parameter("graphql_url").value
        self.trail_id = int(self.get_parameter("trail_id").value)
        self.poll_seconds = float(self.get_parameter("poll_seconds").value)
        self.frame_id = str(self.get_parameter("frame_id").value)

        self.path_pub = self.create_publisher(Path, "/trailintel/route_path", 10)
        self.pose_array_pub = self.create_publisher(PoseArray, "/trailintel/route_pose_array", 10)
        self.risk_pub = self.create_publisher(Float32, "/trailintel/route_risk_score", 10)
        self.status_pub = self.create_publisher(String, "/trailintel/route_status_json", 10)
        self.selected_trail_sub = self.create_subscription(
            Int32, "/trailintel/select_trail_id", self._on_selected_trail, 10
        )

        self.timer = self.create_timer(self.poll_seconds, self._tick)
        self.get_logger().info(
            f"TrailIntel ROS bridge started; polling {self.graphql_url} for trail_id={self.trail_id}"
        )

    def _on_selected_trail(self, msg: Int32) -> None:
        new_trail_id = int(msg.data)
        if new_trail_id <= 0:
            self.get_logger().warning(f"Ignoring invalid trail_id {new_trail_id}")
            return
        self.trail_id = new_trail_id
        self.get_logger().info(f"Switched bridge trail_id to {self.trail_id}")
        self._tick()

    def _tick(self) -> None:
        payload = self._fetch_trail_payload(self.trail_id)
        if not payload:
            return
        points = route_points_from_payload(payload)
        status = bridge_status_from_payload(payload)
        self._publish_path(points)
        self._publish_pose_array(points)
        self._publish_risk(float(status["risk_score"]))
        self._publish_status(status)

    def _fetch_trail_payload(self, trail_id: int) -> Optional[Dict[str, Any]]:
        body = json.dumps(graphql_body_for_trail(trail_id)).encode("utf-8")
        req = request.Request(
            self.graphql_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=8) as response:
                if response.status != 200:
                    self.get_logger().error(f"GraphQL request failed with HTTP {response.status}")
                    return None
                payload = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            self.get_logger().error(f"Failed fetching TrailIntel GraphQL payload: {exc}")
            return None

        if payload.get("errors"):
            self.get_logger().error(f"GraphQL returned errors: {payload['errors']}")
            return None
        if not (payload.get("data") or {}).get("roboticsTraversability"):
            self.get_logger().warning(f"No robotics payload returned for trail_id={trail_id}")
            return None
        return payload

    def _publish_path(self, points: List[Dict[str, float]]) -> None:
        msg = Path()
        now = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        msg.header.stamp = now
        for point in points:
            pose_stamped = PoseStamped()
            pose_stamped.header.frame_id = self.frame_id
            pose_stamped.header.stamp = now
            pose_stamped.pose.position.x = float(point["x"])
            pose_stamped.pose.position.y = float(point["y"])
            pose_stamped.pose.position.z = float(point["z"])
            pose_stamped.pose.orientation.w = 1.0
            msg.poses.append(pose_stamped)
        self.path_pub.publish(msg)

    def _publish_pose_array(self, points: List[Dict[str, float]]) -> None:
        msg = PoseArray()
        msg.header.frame_id = self.frame_id
        msg.header.stamp = self.get_clock().now().to_msg()
        for point in points:
            pose = Pose()
            pose.position.x = float(point["x"])
            pose.position.y = float(point["y"])
            pose.position.z = float(point["z"])
            pose.orientation.w = 1.0
            msg.poses.append(pose)
        self.pose_array_pub.publish(msg)

    def _publish_risk(self, risk_score: float) -> None:
        msg = Float32()
        msg.data = float(risk_score)
        self.risk_pub.publish(msg)

    def _publish_status(self, status: Dict[str, Any]) -> None:
        msg = String()
        msg.data = json.dumps(status)
        self.status_pub.publish(msg)


def main() -> None:  # pragma: no cover - entrypoint
    rclpy.init()
    node = TrailIntelBridgeNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
