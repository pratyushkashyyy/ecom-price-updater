#!/usr/bin/env python3
"""
Utility functions to clean up Chrome/ChromeDriver processes
"""
import os
import subprocess
import psutil
import signal


def kill_chrome_processes(force=False, only_orphaned=False):
    """
    Kill Chrome/ChromeDriver processes to prevent memory leaks.
    
    Args:
        force: If True, use SIGKILL instead of SIGTERM
        only_orphaned: If True, only kill orphaned/zombie processes, not active ones
    """
    killed_count = 0
    processes_to_kill = ['chrome', 'chromium', 'chromedriver', 'undetected_chromedriver']
    current_pid = os.getpid()
    
    for proc_name in processes_to_kill:
        try:
            # Find all processes matching the name
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'ppid', 'status', 'create_time']):
                try:
                    proc_info = proc.info
                    name = proc_info.get('name', '').lower()
                    cmdline = ' '.join(proc_info.get('cmdline', [])).lower()
                    
                    # Skip current process
                    if proc_info['pid'] == current_pid:
                        continue
                    
                    # Match process name or command line
                    if proc_name.lower() in name or proc_name.lower() in cmdline:
                        # Skip if it's a system process or important process
                        if 'google-chrome' in cmdline and '--type=zygote' in cmdline:
                            continue
                        
                        # If only_orphaned is True, check if process is orphaned
                        if only_orphaned:
                            should_kill = False
                            try:
                                # Check if process is zombie (definitely orphaned)
                                if proc_info.get('status') == psutil.STATUS_ZOMBIE:
                                    should_kill = True
                                # Check if parent process is dead (orphaned)
                                elif proc_info.get('ppid'):
                                    try:
                                        parent = psutil.Process(proc_info['ppid'])
                                        if not parent.is_running():
                                            should_kill = True  # Parent is dead, process is orphaned
                                        # If parent is alive, don't kill (even if old)
                                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                                        # Can't check parent - be conservative and skip
                                        # (might be a permission issue, not necessarily orphaned)
                                        continue
                                # If no parent info and process is very old (>1 hour), likely orphaned
                                elif proc_info.get('create_time'):
                                    import time
                                    age = time.time() - proc_info['create_time']
                                    if age >= 3600:  # More than 1 hour old
                                        should_kill = True  # Very old, likely orphaned
                                    else:
                                        continue  # Too new, definitely skip
                                else:
                                    # No way to determine if orphaned - skip to be safe
                                    continue
                                
                                if not should_kill:
                                    continue  # Not orphaned, skip
                            except Exception:
                                # If we can't determine, skip it to be safe
                                continue
                        
                        try:
                            if force:
                                proc.kill()  # SIGKILL
                            else:
                                proc.terminate()  # SIGTERM
                            killed_count += 1
                            print(f"  ✓ Killed process: {proc_name} (PID: {proc_info['pid']})")
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                            pass
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as e:
            # Don't use killall as fallback when only_orphaned is True (too aggressive)
            if not only_orphaned:
                try:
                    if force:
                        subprocess.run(['killall', '-9', proc_name], 
                                     capture_output=True, timeout=5)
                    else:
                        subprocess.run(['killall', proc_name], 
                                     capture_output=True, timeout=5)
                except:
                    pass
    
    return killed_count


def cleanup_chrome_driver(driver, timeout=5):
    """
    Safely cleanup a Chrome driver instance.
    Only kills processes related to this specific driver, not all Chrome processes.
    
    Args:
        driver: Selenium WebDriver instance
        timeout: Timeout in seconds for quit operation
    """
    if driver is None:
        return
    
    try:
        # Try normal quit first - this should clean up the driver's processes
        driver.quit()
    except Exception as e:
        try:
            # If quit fails, try close
            driver.close()
        except Exception as e2:
            pass
    
    # Wait a bit for processes to cleanup naturally
    import time
    time.sleep(0.5)
    
    # Only kill orphaned processes (zombies, dead parents, very old processes)
    # This prevents killing active Chrome processes from other concurrent scrapes
    try:
        killed = kill_chrome_processes(force=False, only_orphaned=True)
        if killed > 0:
            print(f"  ⚠️  Cleaned up {killed} orphaned Chrome processes after driver.quit()")
    except:
        pass


if __name__ == "__main__":
    print("Cleaning up Chrome processes...")
    killed = kill_chrome_processes(force=True)
    print(f"Killed {killed} Chrome/ChromeDriver processes")


