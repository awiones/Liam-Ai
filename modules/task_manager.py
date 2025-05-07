import psutil
import platform
import subprocess
from datetime import datetime

class TaskManager:
    """
    TaskManager class for accessing and analyzing system processes.
    Provides methods to get running processes and their details.
    """
    
    def __init__(self):
        """Initialize the TaskManager with system‐specific settings."""
        self.system = platform.system()
        self.process_cache = {}
        self.last_update = None
        self.cache_ttl = 5  # Time in seconds before refreshing process cache
    
    def get_running_processes(self):
        """
        Get a list of all running processes.
        Returns a list of dictionaries with process information.
        """
        current_time = datetime.now()
        if (self.last_update and 
            (current_time - self.last_update).total_seconds() < self.cache_ttl and 
            self.process_cache):
            return self.process_cache
            
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status']):
            try:
                proc_info = proc.info
                proc_info['created'] = datetime.fromtimestamp(proc.create_time()).strftime("%Y-%m-%d %H:%M:%S")
                try:
                    proc_info['cmdline'] = ' '.join(proc.cmdline())
                except (psutil.AccessDenied, psutil.ZombieProcess):
                    proc_info['cmdline'] = "Access denied"
                processes.append(proc_info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
        self.process_cache = processes
        self.last_update = current_time
        
        return processes
    
    def get_process_details(self, pid):
        """
        Get detailed information about a specific process by PID.
        Returns a dictionary with process details.
        """
        try:
            proc = psutil.Process(pid)
            details = {
                'pid': proc.pid,
                'name': proc.name(),
                'status': proc.status(),
                'username': proc.username(),
                'cpu_percent': proc.cpu_percent(),
                'memory_percent': proc.memory_percent(),
                'created': datetime.fromtimestamp(proc.create_time()).strftime("%Y-%m-%d %H:%M:%S"),
                'connections': len(proc.connections()),
                'threads': len(proc.threads()),
            }
            
            try:
                details['cmdline'] = ' '.join(proc.cmdline())
            except (psutil.AccessDenied, psutil.ZombieProcess):
                details['cmdline'] = "Access denied"
                
            return details
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
    
    def describe_processes(self, limit=10, sort_by='cpu_percent', detail_level='normal', speak_summary=False):
        """
        Generate a human-readable description of running processes.
        
        Args:
            limit: Maximum number of processes to include in description
            sort_by: Field to sort by ('cpu_percent', 'memory_percent', or 'created')
            detail_level: 'minimal', 'normal', or 'detailed'
            speak_summary: If True, return a short summary for speech instead of full details
            
        Returns:
            A string description of the current system processes
        """
        processes = self.get_running_processes()
        
        if sort_by == 'cpu_percent':
            processes.sort(key=lambda p: p.get('cpu_percent', 0), reverse=True)
        elif sort_by == 'memory_percent':
            processes.sort(key=lambda p: p.get('memory_percent', 0), reverse=True)
        elif sort_by == 'created':
            processes.sort(key=lambda p: p.get('created', ''), reverse=True)
        
        processes = processes[:limit]
        
        if not processes:
            return "No processes found or unable to access process information."
        
        if detail_level == 'minimal':
            description = f"Top {len(processes)} running processes: "
            process_list = [f"{p.get('name', 'Unknown')} (PID: {p.get('pid', 'N/A')})" for p in processes]
            description += ", ".join(process_list)
        
        elif detail_level == 'detailed':
            description = f"System running {len(self.process_cache)} total processes. Top {len(processes)} by {sort_by}:\n\n"
            for p in processes:
                description += f"- {p.get('name', 'Unknown')} (PID: {p.get('pid', 'N/A')})\n"
                description += f"  CPU: {p.get('cpu_percent', 0):.1f}%, Memory: {p.get('memory_percent', 0):.1f}%\n"
                description += f"  User: {p.get('username', 'Unknown')}, Status: {p.get('status', 'Unknown')}\n"
                description += f"  Started: {p.get('created', 'Unknown')}\n"
                if p.get('cmdline'):
                    description += f"  Command: {p.get('cmdline')[:60]}{'...' if len(p.get('cmdline', '')) > 60 else ''}\n"
                description += "\n"
        
        else:  # normal detail level
            description = f"Currently running {len(self.process_cache)} processes. Top {len(processes)} by {sort_by}:\n"
            for p in processes:
                description += f"- {p.get('name', 'Unknown')} (PID: {p.get('pid', 'N/A')}): "
                description += f"CPU {p.get('cpu_percent', 0):.1f}%, Mem {p.get('memory_percent', 0):.1f}%, "
                description += f"Status: {p.get('status', 'Unknown')}\n"
        
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        description += f"\nOverall system usage: CPU {cpu_percent}%, Memory {memory.percent}% used."
        
        if speak_summary:
            return f"Currently running {len(self.process_cache)} processes. Top process by {sort_by}: {processes[0].get('name', 'Unknown')} using {processes[0].get('cpu_percent', 0):.1f}% CPU."
        
        return description
    
    def find_process_by_name(self, name):
        """
        Find processes by name (case-insensitive, partial match).
        Returns a list of matching processes.
        """
        processes = self.get_running_processes()
        name = name.lower()
        
        matching_processes = [p for p in processes if name in p.get('name', '').lower()]
        return matching_processes
    
    def get_system_resource_usage(self):
        """
        Get overall system resource usage.
        Returns a dictionary with CPU, memory, disk, and network usage.
        """
        cpu_percent = psutil.cpu_percent(interval=0.5)
        virtual_memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        info = {
            'cpu_percent': cpu_percent,
            'memory': {
                'total': virtual_memory.total,
                'available': virtual_memory.available,
                'percent': virtual_memory.percent,
                'used': virtual_memory.used,
                'free': virtual_memory.free
            },
            'disk': {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': disk.percent
            },
            'boot_time': datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return info
    
    def kill_process(self, pid):
        """
        Attempt to terminate a process by PID.
        Returns True if successful, False otherwise.
        """
        try:
            process = psutil.Process(pid)
            process.terminate()
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
    
    def analyze_user_query(self, query):
        """
        Intelligently analyze a user's query about processes or system resources
        and provide a targeted response.
        
        Args:
            query: String containing the user's question or request
            
        Returns:
            A relevant response addressing the specific question
        """
        query = query.lower()
        
        # Check for specific process queries
        if any(app in query for app in ["chrome", "google chrome", "browser"]):
            chrome_processes = self.find_process_by_name("chrome")
            if chrome_processes:
                total_chrome_cpu = sum(p.get('cpu_percent', 0) for p in chrome_processes)
                total_chrome_memory = sum(p.get('memory_percent', 0) for p in chrome_processes)
                
                return (f"Yes, Google Chrome is running with {len(chrome_processes)} processes. "
                        f"Chrome is using {total_chrome_cpu:.1f}% CPU and {total_chrome_memory:.1f}% memory in total.")
            else:
                return "No, Google Chrome doesn't appear to be running at the moment."
        
        # Check for "suspicious" or unusual processes
        if any(term in query for term in ["suspicious", "unusual", "strange", "weird", "malware", "virus"]):
            processes = self.get_running_processes()
            processes.sort(key=lambda p: p.get('cpu_percent', 0), reverse=True)
            
            high_cpu_procs = [p for p in processes if p.get('cpu_percent', 0) > 15]
            
            if high_cpu_procs:
                response = "I noticed these processes with unusually high CPU usage:\n"
                for p in high_cpu_procs[:3]:  # Show top 3 CPU users
                    response += f"- {p.get('name', 'Unknown')} using {p.get('cpu_percent', 0):.1f}% CPU\n"
                response += "\nHigh CPU usage isn't necessarily suspicious but might be worth checking."
                return response
            else:
                return "I didn't detect any processes with unusually high resource usage that might be suspicious."
        
        # Check for resource hog queries
        if any(term in query for term in ["using most", "highest", "top process", "resource hog", "cpu hog", "memory hog"]):
            processes = self.get_running_processes()
            
            if "cpu" in query or "processor" in query:
                processes.sort(key=lambda p: p.get('cpu_percent', 0), reverse=True)
                top_proc = processes[0]
                return f"The process using the most CPU is {top_proc.get('name', 'Unknown')} (PID: {top_proc.get('pid', 'N/A')}) at {top_proc.get('cpu_percent', 0):.1f}% CPU usage."
            
            elif "memory" in query or "ram" in query:
                processes.sort(key=lambda p: p.get('memory_percent', 0), reverse=True)
                top_proc = processes[0]
                return f"The process using the most memory is {top_proc.get('name', 'Unknown')} (PID: {top_proc.get('pid', 'N/A')}) at {top_proc.get('memory_percent', 0):.1f}% memory usage."
            
            else:
                processes.sort(key=lambda p: p.get('cpu_percent', 0), reverse=True)
                top_proc = processes[0]
                return f"The top resource-using process is {top_proc.get('name', 'Unknown')} at {top_proc.get('cpu_percent', 0):.1f}% CPU and {top_proc.get('memory_percent', 0):.1f}% memory."
        
        # Check for "should I end/kill/terminate" queries
        if any(term in query for term in ["should i end", "should i kill", "should i terminate", "can i close"]):
            words = query.split()
            action_words = ["end", "kill", "terminate", "close"]
            action_positions = [i for i, word in enumerate(words) if word in action_words]
            
            if action_positions:
                pos = action_positions[0]
                if pos + 1 < len(words):
                    process_name = words[pos + 1]
                    if process_name in ["it", "this", "that", "the", "a", "an"]:
                        if pos + 2 < len(words):
                            process_name = words[pos + 2]
                        else:
                            return "I'm not sure which process you're asking about."
                    
                    critical_processes = ["system", "explorer.exe", "winlogon.exe", "services.exe", "lsass.exe", "svchost.exe"]
                    if process_name.lower() in critical_processes:
                        return f"I wouldn't recommend terminating {process_name} as it appears to be a critical system process. Doing so could cause system instability."
                    
                    matching = self.find_process_by_name(process_name)
                    if matching:
                        if any(p.get('cpu_percent', 0) > 20 for p in matching):
                            return f"{process_name} seems to be using significant CPU resources. If it's not responding, you might consider terminating it, but save your work in other applications first."
                        else:
                            return f"{process_name} is running but not using excessive resources. I'd only terminate it if it's not responding."
                    else:
                        return f"I couldn't find any running processes matching '{process_name}'."
            
            return "I need to know which process you're asking about terminating."
        
        # General system health query
        if any(term in query for term in ["system health", "is my computer ok", "computer running well", "pc health", "laptop health"]):
            resources = self.get_system_resource_usage()
            
            if resources['cpu_percent'] > 80:
                cpu_status = "Your CPU is under very heavy load."
            elif resources['cpu_percent'] > 50:
                cpu_status = "Your CPU is under moderate load."
            else:
                cpu_status = "Your CPU load is normal."
                
            if resources['memory']['percent'] > 85:
                mem_status = "Your memory usage is very high."
            elif resources['memory']['percent'] > 65:
                mem_status = "Your memory usage is moderately high."
            else:
                mem_status = "Your memory usage is normal."
                
            if resources['disk']['percent'] > 90:
                disk_status = "Your system disk is almost full."
            elif resources['disk']['percent'] > 75:
                disk_status = "Your system disk is getting full."
            else:
                disk_status = "Your disk space usage is normal."
                
            return f"System health check: {cpu_status} {mem_status} {disk_status} Overall, your system is running {'with possible issues' if resources['cpu_percent'] > 70 or resources['memory']['percent'] > 80 else 'normally'}."
            
        return None  