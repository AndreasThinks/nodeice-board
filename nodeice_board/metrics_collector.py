"""
Metrics Collector for Nodeice Board.

This module collects and stores metrics about the Nodeice Board system,
including system information, node status, and usage statistics.
"""

import os
import time
import logging
import threading
import sqlite3
import platform
from datetime import datetime
from typing import Dict, Any, List, Optional

class MetricsCollector:
    """
    Collects and stores metrics about the Nodeice Board system.
    
    This class runs in a background thread and periodically collects metrics
    about the system, including:
    - Number of connected nodes
    - System uptime
    - CPU usage
    - Memory usage
    - Disk usage
    - Number of active posts
    - Number of comments
    - Number of users
    """
    
    def __init__(self, database, mesh_interface, collection_interval_seconds=300):
        """
        Initialize the metrics collector.
        
        Args:
            database: The database instance.
            mesh_interface: The Meshtastic interface instance.
            collection_interval_seconds: How often to collect metrics (in seconds).
        """
        self.db = database
        self.mesh_interface = mesh_interface
        self.collection_interval = collection_interval_seconds
        self.logger = logging.getLogger("NodeiceBoard")
        self.running = False
        self.thread = None
        self.start_time = time.time()
        
        # Ensure metrics table exists
        self._create_metrics_table()
        self._create_node_status_table()
        
    def _create_metrics_table(self):
        """Create the metrics table if it doesn't exist."""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    timestamp TEXT NOT NULL
                )
            ''')
            
            # Create index on metric_name and timestamp for faster queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_metrics_name_time 
                ON metrics(metric_name, timestamp)
            ''')
            
            conn.commit()
        except Exception as e:
            self.logger.error(f"Error creating metrics table: {e}")
            
    def _create_node_status_table(self):
        """Create the node status table if it doesn't exist."""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS node_status (
                    node_id TEXT PRIMARY KEY,
                    node_name TEXT,
                    status TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    battery_level REAL,
                    signal_strength REAL,
                    latitude REAL,
                    longitude REAL,
                    altitude REAL
                )
            ''')
            
            conn.commit()
        except Exception as e:
            self.logger.error(f"Error creating node_status table: {e}")
            
    def start(self):
        """Start the metrics collection thread."""
        if self.running:
            self.logger.warning("Metrics collector is already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.thread.start()
        self.logger.info("Metrics collector started")
        
    def stop(self):
        """Stop the metrics collection thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5.0)
            self.thread = None
        self.logger.info("Metrics collector stopped")
        
    def _collection_loop(self):
        """Main collection loop that runs in a background thread."""
        while self.running:
            try:
                self._collect_and_store_metrics()
            except Exception as e:
                self.logger.error(f"Error collecting metrics: {e}")
                
            # Sleep for the collection interval
            for _ in range(int(self.collection_interval / 10)):
                if not self.running:
                    break
                time.sleep(10)
                
    def _collect_and_store_metrics(self):
        """Collect metrics and store them in the database."""
        self.logger.debug("Collecting metrics")
        
        metrics = {}
        
        # Collect system metrics
        metrics.update(self._collect_system_metrics())
        
        # Collect node metrics
        metrics.update(self._collect_node_metrics())
        
        # Collect database metrics
        metrics.update(self._collect_database_metrics())
        
        # Store metrics in the database
        self._store_metrics(metrics)
        
        self.logger.debug(f"Collected {len(metrics)} metrics")
        
    def _collect_system_metrics(self) -> Dict[str, float]:
        """
        Collect system metrics.
        
        Returns:
            Dictionary of metric name to value.
        """
        metrics = {}
        
        # System uptime (seconds since this process started)
        metrics["system_uptime_seconds"] = time.time() - self.start_time
        
        # Try to get CPU temperature (Raspberry Pi specific)
        try:
            if os.path.exists('/sys/class/thermal/thermal_zone0/temp'):
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp = float(f.read().strip()) / 1000.0
                    metrics["cpu_temperature_celsius"] = temp
        except Exception as e:
            self.logger.debug(f"Could not read CPU temperature: {e}")
            
        # Memory usage
        try:
            import psutil
            memory = psutil.virtual_memory()
            metrics["memory_used_percent"] = memory.percent
            metrics["memory_available_mb"] = memory.available / (1024 * 1024)
            
            # CPU usage
            metrics["cpu_percent"] = psutil.cpu_percent(interval=1)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            metrics["disk_used_percent"] = disk.percent
            metrics["disk_free_mb"] = disk.free / (1024 * 1024)
            
        except ImportError:
            self.logger.debug("psutil not available, skipping detailed system metrics")
            
        return metrics
        
    def _collect_node_metrics(self) -> Dict[str, float]:
        """
        Collect node metrics from the Meshtastic interface.
        
        Returns:
            Dictionary of metric name to value.
        """
        metrics = {}
        
        try:
            # Get connected nodes from the mesh interface
            if self.mesh_interface and hasattr(self.mesh_interface, 'get_nodes'):
                nodes = self.mesh_interface.get_nodes()
                
                # Count active nodes
                active_nodes = 0
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Update node status in the database
                conn = self.db.get_connection()
                cursor = conn.cursor()
                
                # First, mark all nodes as inactive
                cursor.execute(
                    "UPDATE node_status SET status = 'inactive' WHERE status = 'active'"
                )
                
                # Then update or insert active nodes
                for node_id, node_info in nodes.items():
                    if node_info.get('active', False):
                        active_nodes += 1
                        
                        # Update or insert node status
                        cursor.execute(
                            """
                            INSERT INTO node_status 
                            (node_id, node_name, status, last_seen, battery_level, signal_strength, 
                             latitude, longitude, altitude) 
                            VALUES (?, ?, 'active', ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(node_id) DO UPDATE SET
                            node_name = excluded.node_name,
                            status = excluded.status,
                            last_seen = excluded.last_seen,
                            battery_level = excluded.battery_level,
                            signal_strength = excluded.signal_strength,
                            latitude = excluded.latitude,
                            longitude = excluded.longitude,
                            altitude = excluded.altitude
                            """,
                            (
                                node_id,
                                node_info.get('name', ''),
                                now,
                                node_info.get('battery_level'),
                                node_info.get('signal_strength'),
                                node_info.get('latitude'),
                                node_info.get('longitude'),
                                node_info.get('altitude')
                            )
                        )
                
                conn.commit()
                
                # Store the active node count
                metrics["active_nodes"] = active_nodes
                
        except Exception as e:
            self.logger.error(f"Error collecting node metrics: {e}")
            
        return metrics
        
    def _collect_database_metrics(self) -> Dict[str, float]:
        """
        Collect metrics from the database.
        
        Returns:
            Dictionary of metric name to value.
        """
        metrics = {}
        
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Count active posts
            cursor.execute("SELECT COUNT(*) FROM posts WHERE visible = 1")
            metrics["active_posts"] = cursor.fetchone()[0]
            
            # Count comments
            cursor.execute("SELECT COUNT(*) FROM comments")
            metrics["total_comments"] = cursor.fetchone()[0]
            
            # Count unique users (post authors + comment authors)
            cursor.execute(
                """
                SELECT COUNT(DISTINCT author_id) FROM 
                (SELECT author_id FROM posts UNION SELECT author_id FROM comments)
                """
            )
            metrics["unique_users"] = cursor.fetchone()[0]
            
            # Count subscriptions
            cursor.execute("SELECT COUNT(*) FROM subscriptions")
            metrics["total_subscriptions"] = cursor.fetchone()[0]
            
            # Database size (if possible)
            try:
                cursor.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                metrics["database_size_kb"] = (page_count * page_size) / 1024
            except Exception as e:
                self.logger.debug(f"Could not get database size: {e}")
                
        except Exception as e:
            self.logger.error(f"Error collecting database metrics: {e}")
            
        return metrics
        
    def _store_metrics(self, metrics: Dict[str, float]):
        """
        Store metrics in the database.
        
        Args:
            metrics: Dictionary of metric name to value.
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Insert each metric
            for name, value in metrics.items():
                cursor.execute(
                    "INSERT INTO metrics (metric_name, metric_value, timestamp) VALUES (?, ?, ?)",
                    (name, value, now)
                )
                
            conn.commit()
            
            # Clean up old metrics (keep only last 30 days)
            thirty_days_ago = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "DELETE FROM metrics WHERE timestamp < datetime('now', '-30 days')"
            )
            conn.commit()
            
        except Exception as e:
            self.logger.error(f"Error storing metrics: {e}")
            
    def get_latest_metrics(self) -> Dict[str, float]:
        """
        Get the latest values for all metrics.
        
        Returns:
            Dictionary of metric name to latest value.
        """
        metrics = {}
        
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Get distinct metric names
            cursor.execute("SELECT DISTINCT metric_name FROM metrics")
            metric_names = [row[0] for row in cursor.fetchall()]
            
            # For each metric name, get the latest value
            for name in metric_names:
                cursor.execute(
                    """
                    SELECT metric_value FROM metrics 
                    WHERE metric_name = ? 
                    ORDER BY timestamp DESC LIMIT 1
                    """,
                    (name,)
                )
                result = cursor.fetchone()
                if result:
                    metrics[name] = result[0]
                    
        except Exception as e:
            self.logger.error(f"Error getting latest metrics: {e}")
            
        return metrics
        
    def get_metric_history(self, metric_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get historical values for a specific metric.
        
        Args:
            metric_name: The name of the metric.
            hours: Number of hours of history to retrieve.
            
        Returns:
            List of dictionaries with 'timestamp' and 'value' keys.
        """
        history = []
        
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT timestamp, metric_value FROM metrics 
                WHERE metric_name = ? AND timestamp > datetime('now', ?) 
                ORDER BY timestamp ASC
                """,
                (metric_name, f"-{hours} hours")
            )
            
            for row in cursor.fetchall():
                history.append({
                    'timestamp': row[0],
                    'value': row[1]
                })
                
        except Exception as e:
            self.logger.error(f"Error getting metric history: {e}")
            
        return history
        
    def get_active_nodes(self) -> List[Dict[str, Any]]:
        """
        Get a list of currently active nodes.
        
        Returns:
            List of dictionaries with node information.
        """
        nodes = []
        
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT node_id, node_name, last_seen, battery_level, signal_strength,
                       latitude, longitude, altitude
                FROM node_status
                WHERE status = 'active'
                ORDER BY last_seen DESC
                """
            )
            
            for row in cursor.fetchall():
                nodes.append({
                    'id': row[0],
                    'name': row[1],
                    'last_seen': row[2],
                    'battery_level': row[3],
                    'signal_strength': row[4],
                    'latitude': row[5],
                    'longitude': row[6],
                    'altitude': row[7]
                })
                
        except Exception as e:
            self.logger.error(f"Error getting active nodes: {e}")
            
        return nodes
