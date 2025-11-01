"""
Virtual Display Setup for Headless Browser Automation
Uses Xvfb (X Virtual Framebuffer) to run browsers without a physical display
"""

import os
import platform
import subprocess
import signal
from typing import Optional
from contextlib import contextmanager


class VirtualDisplay:
    """Manages a virtual X display using Xvfb"""
    
    def __init__(self, display_num: int = 99, width: int = 1920, height: int = 1080, depth: int = 24):
        self.display_num = display_num
        self.width = width
        self.height = height
        self.depth = depth
        self.display_var = f":{display_num}"
        self.xvfb_process: Optional[subprocess.Popen] = None
        self.original_display: Optional[str] = None
        self.is_active = False
    
    def start(self) -> bool:
        """Start the virtual display"""
        if self.is_active:
            return True
        
        # Check if running on Linux (Xvfb is Linux-only)
        if platform.system() != 'Linux':
            print(f"⚠️  Virtual display (Xvfb) is only available on Linux.")
            print(f"   Current OS: {platform.system()}")
            print(f"   Running in pseudo-headless mode (browser will run but be minimized)")
            return False
        
        # Check if Xvfb is installed
        try:
            subprocess.run(['which', 'Xvfb'], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  Xvfb not found. Install it with: sudo apt-get install xvfb")
            return False
        
        try:
            # Start Xvfb
            cmd = [
                'Xvfb',
                self.display_var,
                '-screen', '0', f'{self.width}x{self.height}x{self.depth}',
                '-ac',  # disable access control
                '-nolisten', 'tcp',  # disable TCP connections
                '-dpi', '96',  # set DPI
                '+extension', 'RANDR'  # enable RANDR extension for resolution changes
            ]
            
            self.xvfb_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait a moment for Xvfb to start
            import time
            time.sleep(0.5)
            
            # Check if Xvfb started successfully
            if self.xvfb_process.poll() is None:
                # Save original DISPLAY variable
                self.original_display = os.environ.get('DISPLAY')
                # Set DISPLAY to virtual display
                os.environ['DISPLAY'] = self.display_var
                self.is_active = True
                print(f"✅ Virtual display started: DISPLAY={self.display_var}")
                return True
            else:
                print(f"❌ Failed to start Xvfb")
                return False
                
        except Exception as e:
            print(f"❌ Error starting virtual display: {e}")
            return False
    
    def stop(self):
        """Stop the virtual display"""
        if not self.is_active:
            return
        
        # Restore original DISPLAY variable
        if self.original_display:
            os.environ['DISPLAY'] = self.original_display
        else:
            os.environ.pop('DISPLAY', None)
        
        # Terminate Xvfb process
        if self.xvfb_process:
            try:
                self.xvfb_process.terminate()
                self.xvfb_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.xvfb_process.kill()
            except Exception as e:
                print(f"Warning: Error stopping Xvfb: {e}")
            finally:
                self.xvfb_process = None
        
        self.is_active = False
        print("✅ Virtual display stopped")
    
    @contextmanager
    def context(self):
        """Context manager for virtual display"""
        started = self.start()
        try:
            yield started
        finally:
            if started:
                self.stop()
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


def setup_virtual_display_for_selenium(options):
    """
    Configure Selenium Chrome options for virtual display
    
    Args:
        options: ChromeOptions object to configure
        
    Returns:
        Modified options object
    """
    # These options work well with virtual display
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')  # GPU not needed in virtual display
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-extensions')
    
    # Set window size
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--start-maximized')
    
    return options


def get_display_mode():
    """
    Determine the best display mode based on OS and available tools
    
    Returns:
        str: 'virtual', 'pseudo_headless', or 'headless'
    """
    system = platform.system()
    
    if system == 'Linux':
        # Check if Xvfb is available
        try:
            subprocess.run(['which', 'Xvfb'], check=True, capture_output=True)
            return 'virtual'
        except:
            return 'pseudo_headless'
    elif system == 'Darwin':  # macOS
        return 'pseudo_headless'
    elif system == 'Windows':
        return 'pseudo_headless'
    else:
        return 'headless'

