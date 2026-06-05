"""Performance monitoring backend for ROS2 topics and nodes."""
import rclpy
from rclpy.node import Node
import psutil
import threading
import time
from collections import defaultdict, deque

try:
    from rosidl_runtime_py.utilities import get_message
    ROSIDL_AVAILABLE = True
except ImportError:
    ROSIDL_AVAILABLE = False


class PerformanceMonitor:
    """Monitor performance metrics for ROS2 topics and nodes."""
    
    def __init__(self):
        """Initialize performance monitor."""
        self.node = None
        self.executor = None
        self.executor_thread = None
        
        # Tracking dictionaries
        self.topic_message_counts = defaultdict(int)
        self.topic_message_times = defaultdict(lambda: deque(maxlen=100))
        self.subscriptions = {}
        
        self._initialize_node()
    
    def _initialize_node(self):
        """Initialize ROS2 node and executor."""
        try:
            if not rclpy.ok():
                rclpy.init()
            
            self.node = rclpy.create_node('ros2_studio_performance_monitor')
            self.executor = rclpy.executors.SingleThreadedExecutor()
            self.executor.add_node(self.node)
            
            # Start executor in separate thread
            self.executor_thread = threading.Thread(
                target=self.executor.spin,
                daemon=True
            )
            self.executor_thread.start()
        except Exception as e:
            print(f"Error initializing performance monitor: {e}")
    
    def get_all_topics(self):
        """Get list of all active topics."""
        if not self.node:
            return []
        
        try:
            topic_list = self.node.get_topic_names_and_types()
            return sorted([topic[0] for topic in topic_list])
        except Exception as e:
            print(f"Error getting topics: {e}")
            return []
    
    def get_all_nodes(self):
        """Get list of all active nodes."""
        if not self.node:
            return []
        
        try:
            node_names = self.node.get_node_names()
            return sorted(node_names)
        except Exception as e:
            print(f"Error getting nodes: {e}")
            return []
    
    def get_topic_metrics(self, topic_name):
        """Get performance metrics for a specific topic."""
        if not self.node:
            return None

        # Ensure we are subscribed so frequency tracking works
        self.subscribe_to_topic(topic_name)

        try:
            # Get system-level metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_info = psutil.virtual_memory()
            memory_mb = memory_info.used / (1024 ** 2)
            
            # Calculate message frequency
            frequency = self._calculate_topic_frequency(topic_name)
            
            # Get publisher/subscriber counts
            publishers = self.node.count_publishers(topic_name)
            subscribers = self.node.count_subscribers(topic_name)
            
            return {
                'cpu': cpu_percent,
                'memory': memory_mb,
                'frequency': frequency,
                'publishers': publishers,
                'subscribers': subscribers,
                'message_count': self.topic_message_counts.get(topic_name, 0)
            }
        except Exception as e:
            print(f"Error getting topic metrics for {topic_name}: {e}")
            return {
                'cpu': 0.0,
                'memory': 0.0,
                'frequency': 0.0,
                'publishers': 0,
                'subscribers': 0,
                'message_count': 0
            }
    
    def get_node_metrics(self, node_name):
        """Get performance metrics for a specific node."""
        try:
            # Get system-level metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_info = psutil.virtual_memory()
            memory_mb = memory_info.used / (1024 ** 2)
            
            # Try to find the process for this node
            node_cpu = 0.0
            node_memory = 0.0
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    if cmdline and node_name in ' '.join(cmdline):
                        node_cpu = proc.cpu_percent(interval=0.1)
                        node_memory = proc.memory_info().rss / (1024 ** 2)
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return {
                'cpu': node_cpu if node_cpu > 0 else cpu_percent,
                'memory': node_memory if node_memory > 0 else memory_mb,
                'frequency': 0.0,
                'publishers': 0,
                'subscribers': 0
            }
        except Exception as e:
            print(f"Error getting node metrics for {node_name}: {e}")
            return {
                'cpu': 0.0,
                'memory': 0.0,
                'frequency': 0.0,
                'publishers': 0,
                'subscribers': 0
            }
    
    def _calculate_topic_frequency(self, topic_name):
        """Calculate the publishing frequency of a topic."""
        times = self.topic_message_times.get(topic_name)
        if not times or len(times) < 2:
            return 0.0
        
        try:
            time_diffs = []
            times_list = list(times)
            for i in range(1, len(times_list)):
                time_diffs.append(times_list[i] - times_list[i-1])
            
            if time_diffs:
                avg_period = sum(time_diffs) / len(time_diffs)
                if avg_period > 0:
                    return 1.0 / avg_period
            return 0.0
        except Exception as e:
            print(f"Error calculating frequency: {e}")
            return 0.0
    
    def _topic_callback(self, msg, topic_name):
        """Callback for topic messages."""
        self.topic_message_counts[topic_name] += 1
        self.topic_message_times[topic_name].append(time.time())
    
    def subscribe_to_topic(self, topic_name):
        """Subscribe to a topic to track message timestamps for frequency."""
        if not self.node or not ROSIDL_AVAILABLE:
            return
        if topic_name in self.subscriptions:
            return

        try:
            topic_list = self.node.get_topic_names_and_types()
            topic_type = None
            for topic, types in topic_list:
                if topic == topic_name and types:
                    topic_type = types[0]
                    break

            if not topic_type:
                return

            msg_class = get_message(topic_type)
            # Use default-arg capture so each lambda binds its own topic_name
            callback = lambda msg, tn=topic_name: self._topic_callback(msg, tn)
            sub = self.node.create_subscription(msg_class, topic_name, callback, 10)
            self.subscriptions[topic_name] = sub
            print(f"Subscribed to {topic_name} ({topic_type})")
        except Exception as e:
            print(f"Could not subscribe to {topic_name}: {e}")
    
    def cleanup(self):
        """Clean up resources."""
        try:
            # Destroy subscriptions
            for sub in self.subscriptions.values():
                try:
                    self.node.destroy_subscription(sub)
                except Exception as e:
                    print(f"Error destroying subscription: {e}")
            
            if self.executor:
                self.executor.shutdown()
            if self.node:
                self.node.destroy_node()
        except Exception as e:
            print(f"Error during cleanup: {e}")
