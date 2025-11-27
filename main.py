#زيادة بوت السيرفر الى 5bot
import os
import subprocess
import sys
import time
import signal
import threading
from pathlib import Path

class BotManager:
    def __init__(self):
        # ...existing code...
        self.bot2_process = None
        self.bot3_process = None
        self.bot4_process = None
        self.bot5_process = None
        self.base_dir = Path(__file__).parent
        self.running = True
        
    def setup_directories(self):
        """إنشاء المجلدات إذا لم تكن موجودة"""
        # ...existing code...
        bot2_dir = self.base_dir / "bot2"
        bot3_dir = self.base_dir / "bot3"
        bot4_dir = self.base_dir / "bot4"
        bot5_dir = self.base_dir / "bot5"
        
        # إنشاء المجلدات
        bot2_dir.mkdir(exist_ok=True)
        bot3_dir.mkdir(exist_ok=True)
        bot4_dir.mkdir(exist_ok=True)
        bot5_dir.mkdir(exist_ok=True)
        
        print(f"📁 Bot2 directory: {bot2_dir}")
        print(f"📁 Bot3 directory: {bot3_dir}")
        print(f"📁 Bot4 directory: {bot4_dir}")
        print(f"📁 Bot5 directory: {bot5_dir}")
        
        # التحقق من وجود ملفات البوت
        bot2_file = bot2_dir / "main.py"
        bot3_file = bot3_dir / "main.py"
        bot4_file = bot4_dir / "main.py"
        bot5_file = bot5_dir / "main.py"
        
        if not bot2_file.exists():
            print(f"⚠️  Warning: {bot2_file} not found!")
        if not bot3_file.exists():
            print(f"⚠️  Warning: {bot3_file} not found!")
        if not bot4_file.exists():
            print(f"⚠️  Warning: {bot4_file} not found!")
        if not bot5_file.exists():
            print(f"⚠️  Warning: {bot5_file} not found!")
            
        return bot2_dir, bot3_dir, bot4_dir, bot5_dir
    
    def run_bot2(self, bot2_dir):
        """تشغيل البوت الثاني مع إعادة التشغيل"""
        while self.running:
            try:
                print("🚀 Starting Bot 2...")
                
                # الانتقال إلى مجلد البوت الثاني
                original_dir = os.getcwd()
                os.chdir(bot2_dir)
                
                # تشغيل البوت الثاني
                self.bot2_process = subprocess.Popen([sys.executable, "main.py"])
                
                # العودة إلى المجلد الأصلي
                os.chdir(original_dir)
                
                print("✅ Bot 2 started successfully!")
                
                # انتظار انتهاء العملية
                self.bot2_process.wait()
                
                print("❌ Bot 2 stopped. Restarting in 5 seconds...")
                time.sleep(5)
                
            except Exception as e:
                print(f"❌ Error running Bot 2: {e}")
                time.sleep(5)
            finally:
                if os.getcwd() != original_dir:
                    os.chdir(original_dir)
    
    def run_bot3(self, bot3_dir):
        """تشغيل البوت الثالث مع إعادة التشغيل"""
        while self.running:
            try:
                print("🚀 Starting Bot 3...")
                
                # الانتقال إلى مجلد البوت الثالث
                original_dir = os.getcwd()
                os.chdir(bot3_dir)
                
                # تشغيل البوت الثالث
                self.bot3_process = subprocess.Popen([sys.executable, "main.py"])
                
                # العودة إلى المجلد الأصلي
                os.chdir(original_dir)
                
                print("✅ Bot 3 started successfully!")
                
                # انتظار انتهاء العملية
                self.bot3_process.wait()
                
                print("❌ Bot 3 stopped. Restarting in 5 seconds...")
                time.sleep(5)
                
            except Exception as e:
                print(f"❌ Error running Bot 3: {e}")
                time.sleep(5)
            finally:
                if os.getcwd() != original_dir:
                    os.chdir(original_dir)
    def run_bot4(self, bot4_dir):
        """تشغيل البوت الرابع مع إعادة التشغيل"""
        while self.running:
            try:
                print("🚀 Starting Bot 4...")
                
                # الانتقال إلى مجلد البوت الثالث
                original_dir = os.getcwd()
                os.chdir(bot4_dir)
                
                # تشغيل البوت الثالث
                self.bot4_process = subprocess.Popen([sys.executable, "main.py"])
                
                # العودة إلى المجلد الأصلي
                os.chdir(original_dir)
                
                print("✅ Bot 4 started successfully!")
                
                # انتظار انتهاء العملية
                self.bot4_process.wait()
                
                print("❌ Bot 4 stopped. Restarting in 5 seconds...")
                time.sleep(5)
                
            except Exception as e:
                print(f"❌ Error running Bot 4: {e}")
                time.sleep(5)
            finally:
                if os.getcwd() != original_dir:
                    os.chdir(original_dir)
    
    def run_bot5(self, bot5_dir):
        """تشغيل البوت الخامس مع إعادة التشغيل"""
        while self.running:
            try:
                print("🚀 Starting Bot 5...")
                original_dir = os.getcwd()
                os.chdir(bot5_dir)
                self.bot5_process = subprocess.Popen([sys.executable, "main.py"])
                os.chdir(original_dir)
                print("✅ Bot 5 started successfully!")
                self.bot5_process.wait()
                print("❌ Bot 5 stopped. Restarting in 5 seconds...")
                time.sleep(5)
            except Exception as e:
                print(f"❌ Error running Bot 5: {e}")
                time.sleep(5)
            finally:
                if os.getcwd() != original_dir:
                    os.chdir(original_dir)
    
    def stop_bots(self):
        """إيقاف البوتات"""
        print("\n⏹️  Stopping all bots...")
        self.running = False
        
        if self.bot2_process:
            try:
                self.bot2_process.terminate()
                print("🔴 Bot 2 stopped")
            except:
                pass
            
        if self.bot3_process:
            try:
                self.bot3_process.terminate()
                print("🔴 Bot 3 stopped")
            except:
                pass
        if self.bot4_process:
            try:
                self.bot4_process.terminate()
                print("🔴 Bot 4 stopped")
            except:
                pass
        if self.bot5_process:
            try:
                self.bot5_process.terminate()
                print("🔴 Bot 5 stopped")
            except:
                pass
    
    def run_all_bots(self):
        """تشغيل البوتات معاً"""
        print("🎯 Starting all bots...")
        
        # إعداد المجلدات
        bot2_dir, bot3_dir, bot4_dir, bot5_dir = self.setup_directories()
        
        # إنشاء threads للبوتات
        bot2_thread = threading.Thread(target=self.run_bot2, args=(bot2_dir,))
        bot3_thread = threading.Thread(target=self.run_bot3, args=(bot3_dir,))
        bot4_thread = threading.Thread(target=self.run_bot4, args=(bot4_dir,))
        bot5_thread = threading.Thread(target=self.run_bot5, args=(bot5_dir,))
        
        # بدء تشغيل البوتات
        bot2_thread.start()
        time.sleep(3)
        bot3_thread.start()
        time.sleep(3)
        bot4_thread.start()
        time.sleep(3)
        bot5_thread.start()
        print("✅ All bots are running!")
        print("🔄 Press Ctrl+C to stop...")
        
        try:
            # انتظار انتهاء البوتات
            bot2_thread.join()
            bot3_thread.join()
            bot4_thread.join()
            bot5_thread.join()
        except KeyboardInterrupt:
            self.stop_bots()

def signal_handler(signum, frame):
    """معالج إشارة الإيقاف"""
    print("\n🛑 Received stop signal...")
    if 'bot_manager' in globals():
        bot_manager.stop_bots()
    sys.exit(0)

def main():
    """الدالة الرئيسية"""
    global bot_manager
    
    # تسجيل معالج الإشارة
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # إنشاء مدير البوتات
    bot_manager = BotManager()
    
    # تشغيل البوتات
    bot_manager.run_all_bots()

if __name__ == "__main__":
    main()
