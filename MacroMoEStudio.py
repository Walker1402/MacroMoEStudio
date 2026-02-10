import sys, json, urllib.request, urllib.error, os, subprocess, base64, re, multiprocessing, time, datetime, threading, gc
import tkinter as tk
from tkinter import messagebox, filedialog, ttk

# --- GUI THEME SETUP ---
HAS_CTK = False
try:
    import customtkinter as ctk
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    HAS_CTK = True
except ImportError:
    pass # Fallback to standard tkinter

# --- CONFIGURATION ---
URL = "http://localhost:11434/api/chat"
BASE_DIR = os.path.join(os.path.expanduser("~"), "ai_studio") 
HISTORY_DIR = os.path.join(BASE_DIR, "chats")
MEMORY_FILE = os.path.join(BASE_DIR, "memory.json")
CPU_CORES = max(1, multiprocessing.cpu_count() - 2)

if not os.path.exists(HISTORY_DIR): os.makedirs(HISTORY_DIR)

# [VERIFIED] Dynamic Model Loading
MODELS = {
    "logic": os.getenv("AI_LOGIC_MODEL", "phi4-mini-reasoning:3.8b-q4_K_M"), 
    "vision": os.getenv("AI_VISION_MODEL", "qwen3-vl:4b"), 
    "chat": os.getenv("AI_CHAT_MODEL", "gemma3:4b")
}

# ==========================================
#        BACKEND: INTELLIGENCE & SAFETY
# ==========================================

class AIBackend:
    def __init__(self):
        self.memory = self.load_json(MEMORY_FILE, default={})
        self.current_chat_id = f"chat_{int(time.time())}"
        self.history = []
        self.stop_signal = False

    def load_json(self, path, default):
        if os.path.exists(path) and os.path.isfile(path):
            try:
                with open(path, "r", encoding='utf-8') as f: return json.load(f)
            except: return default
        return default

    def save_memory(self):
        with open(MEMORY_FILE, "w", encoding='utf-8') as f: json.dump(self.memory, f)

    def save_chat_history(self):
        filepath = os.path.join(HISTORY_DIR, f"{self.current_chat_id}.json")
        with open(filepath, "w", encoding='utf-8') as f: json.dump(self.history, f)

    def load_chat_history(self, filename):
        filepath = os.path.join(HISTORY_DIR, filename)
        self.history = self.load_json(filepath, default=[])
        self.current_chat_id = filename.replace(".json", "")
        return self.history

    def get_chat_list(self):
        if not os.path.exists(HISTORY_DIR): return []
        files = [f for f in os.listdir(HISTORY_DIR) if f.endswith(".json")]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(HISTORY_DIR, x)), reverse=True)
        return files
    
    def delete_chat(self, filename):
        filepath = os.path.join(HISTORY_DIR, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                return True
            except:
                return False
        return False

    def stop_generation(self):
        self.stop_signal = True

    # [FINAL SECURITY CHECK]
    def execute_command(self, cmd):
        if not cmd or not cmd.strip():
            return "Error: No command provided."

        # 1. Block Shell Operators & Newlines to prevent "Command Injection"
        #    Blocks: chaining (; & |), redirection (> <), subshells (` $), and multiline attacks (\n \r)
        forbidden_chars = [";", "&", "|", ">", "<", "`", "$", "\n", "\r"]
        if any(char in cmd for char in forbidden_chars):
            return "Blocked: Special characters and command chaining are disabled for security."

        # 2. Strict Whitelist (Cross-Platform)
        allowed_commands = [
            "ipconfig", "ifconfig", "ip", # Network
            "dir", "ls",                  # File System
            "ping", "netstat",            # Utilities
            "systeminfo", "whoami",       # Info
            "echo", "date", "time"        # Basics
        ]
        
        # Extract the base command (e.g., 'ping' from 'ping google.com')
        base_cmd = cmd.strip().split()[0].lower()
        
        if base_cmd not in allowed_commands:
            return f"Blocked: '{base_cmd}' is not in the authorized whitelist."
        
        try:
            # shell=True is safe here ONLY because we filtered operators above.
            # It is required for 'dir' on Windows.
            res = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=10)
            return f"Output:\n{res.decode('utf-8', errors='ignore')}"
        except subprocess.TimeoutExpired:
            return "Error: Command timed out."
        except Exception as e: 
            return f"Error: {str(e)}"

    def get_system_context(self, prompt, attached_files=[]):
        ctx = [f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"]
        ctx.append(f"OS: {os.name} ({sys.platform})")
        
        if self.memory:
            ctx.append("User Facts:\n" + "\n".join([f"- {v}" for v in self.memory.values()]))

        for file_path in attached_files:
            if os.path.exists(file_path):
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.exe', '.zip')):
                    continue
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(2000)
                        if len(content) == 2000: content += "... [Truncated]"
                        ctx.append(f"--- FILE: {os.path.basename(file_path)} ---\n{content}")
                except: pass
        return "\n".join(ctx)

    def generate(self, prompt, attached_files=[], force_logic=False, callback=None):
        self.stop_signal = False
        p_clean = prompt.strip()
        
        if p_clean.startswith("/"):
            response_text = ""
            if p_clean.startswith("/remember"):
                self.memory[str(len(self.memory)+1)] = p_clean.replace("/remember","").strip()
                self.save_memory()
                response_text = "Memory Saved."
            elif p_clean.startswith("/forget"):
                self.memory = {}
                self.save_memory()
                response_text = "Memory Wiped."
            if callback and response_text: callback("stream", response_text)
            return response_text

        gc.collect()
        sys_ctx = self.get_system_context(prompt, attached_files)
        
        # --- ROUTER LOGIC ---
        triggers = ["code", "math", "plan", "calc", "network", "ping", "internet", "status", "cmd", "ipconfig", "ifconfig", "ls", "dir"]
        is_logic_needed = any(w in prompt.lower() for w in triggers)
        has_image = any(f.lower().endswith(('.png', '.jpg', '.jpeg')) for f in attached_files)

        # Priority Chain: Force Logic > Image Present > Keyword Trigger > Default Chat
        if force_logic:
            model = MODELS["logic"]
        elif has_image:
            model = MODELS["vision"]
        elif is_logic_needed:
            model = MODELS["logic"]
        else:
            model = MODELS["chat"]

        # Only load image data if we are actually using the vision model
        img_b64 = None
        is_vision_task = (model == MODELS["vision"])
        
        if is_vision_task:
            for f in attached_files:
                if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                    try:
                        with open(f, "rb") as img_f: 
                            img_b64 = base64.b64encode(img_f.read()).decode('utf-8')
                    except Exception as e:
                        if callback: callback("stream", f"[System Error loading image: {e}]")
                    break

        if callback: callback("status", f"Switching to {model}...")

        system_persona = (
            "You are a helpful desktop assistant. "
            "GUIDELINES:\n"
            "1. For greetings ('hello') or general questions, answer NORMALLY in plain text. "
            "2. ONLY use <cmd>...</cmd> tags if the user specifically asks for a system task "
            "(like checking network, listing files, or running a script). "
            "\n"
            "Example 1: User 'Hi' -> You: 'Hello! How can I help?'\n"
            "Example 2: User 'Check IP' -> You: '<cmd>ipconfig</cmd>'"
        )
        
        msgs = [{"role": "system", "content": f"{system_persona}\nCONTEXT:\n{sys_ctx}"}] + self.history[-10:]
        u_msg = {"role": "user", "content": prompt}
        if img_b64: u_msg["images"] = [img_b64]
        msgs.append(u_msg)

        timeout_val = 120 if is_vision_task else 30

        data = {
            "model": model, 
            "messages": msgs, 
            "stream": True,
            "options": {"num_ctx": 4096, "temperature": 0.3}, 
            "keep_alive": "5m"
        }

        try:
            req = urllib.request.Request(URL, data=json.dumps(data).encode('utf-8'))
            full_res = ""
            buffer = ""
            is_thinking = False
            
            if is_vision_task and callback: callback("status", "Processing Image (This may take 30s)...")
            
            with urllib.request.urlopen(req, timeout=timeout_val) as response:
                for line in response:
                    if self.stop_signal:
                        if callback: callback("status", "Stopped by User.")
                        return full_res + " [STOPPED]"

                    if not line: continue
                    try:
                        chunk = json.loads(line.decode())
                    except json.JSONDecodeError: continue

                    text = chunk.get('message', {}).get('content', '')
                    full_res += text
                    buffer += text
                    
                    while True:
                        if is_thinking:
                            end_idx = buffer.find("</think>")
                            if end_idx != -1:
                                is_thinking = False
                                buffer = buffer[end_idx+8:] 
                                if callback: callback("status", "Answering...")
                            else:
                                if len(buffer) > 50: buffer = buffer[-20:]
                                break
                        else:
                            start_idx = buffer.find("<think>")
                            if start_idx != -1:
                                if start_idx > 0 and callback: 
                                    callback("stream", buffer[:start_idx])
                                is_thinking = True
                                buffer = buffer[start_idx+7:]
                                if callback: callback("status", "Thinking... (Hiding Output)")
                            else:
                                potential_tag = False
                                for i in range(1, 8): 
                                    if buffer.endswith("<think>"[:i]):
                                        potential_tag = True
                                        break
                                if not potential_tag:
                                    if callback: callback("stream", buffer)
                                    buffer = ""
                                break

            cmd_match = re.search(r"<cmd>(.*?)</cmd>", full_res, re.DOTALL)
            if cmd_match:
                command_content = cmd_match.group(1).strip()
                if command_content.lower() in ["hello", "hi", "hey", "test", "cmd"]:
                    cmd_match = None 

            if cmd_match and callback: 
                callback("approval_request", cmd_match.group(1).strip())
            
            clean_res = re.sub(r"<think>.*?</think>", "", full_res, flags=re.DOTALL).strip()
            self.history.append({"role": "user", "content": prompt})
            if "images" in u_msg: del u_msg["images"] 
            self.history.append({"role": "assistant", "content": clean_res})
            self.save_chat_history()
            return clean_res

        except urllib.error.URLError:
            return "Error: Could not connect to Ollama. Is it running?"
        except Exception as e:
            return f"Error: {str(e)}"

    def new_chat(self):
        self.history = []
        self.current_chat_id = f"chat_{int(time.time())}"
        return "New Chat Started."

# ==========================================
#        FRONTEND: FULL DESKTOP GUI
# ==========================================

BaseClass = ctk.CTk if HAS_CTK else tk.Tk

class App(BaseClass):
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self.title("Macro-MoE Studio (Safe Mode)")
        self.geometry("950x700")
        
        if HAS_CTK: 
            self.configure(fg_color="#1a1a1a")
            self.grid_columnconfigure(1, weight=1)
            self.grid_rowconfigure(0, weight=1)
        else:
            self.configure(bg="#333")
            self.columnconfigure(1, weight=1)
            self.rowconfigure(0, weight=1)

        # --- SIDEBAR ---
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0) if HAS_CTK else tk.Frame(self, width=200, bg="#222")
        self.sidebar.grid(row=0, column=0, rowspan=3, sticky="nsew")
        
        lbl_cls = ctk.CTkLabel if HAS_CTK else tk.Label
        kw_lbl = {"text": "History", "font": ("Arial", 16, "bold")}
        if not HAS_CTK: kw_lbl.update({"fg": "white", "bg": "#222"})
        self.sidebar_lbl = lbl_cls(self.sidebar, **kw_lbl)
        self.sidebar_lbl.pack(pady=10)

        self.history_list = tk.Listbox(self.sidebar, bg="#2b2b2b", fg="white", borderwidth=0, selectbackground="#444")
        self.history_list.pack(fill="both", expand=True, padx=5, pady=5)
        self.history_list.bind("<<ListboxSelect>>", self.load_selected_chat)

        btn_cls = ctk.CTkButton if HAS_CTK else tk.Button
        self.new_chat_btn = btn_cls(self.sidebar, text="+ New Chat", command=self.start_new_chat)
        self.new_chat_btn.pack(pady=(10, 5), padx=10)

        del_kw = {"text": "Delete Selected", "command": self.delete_selected_chat}
        if HAS_CTK: del_kw.update({"fg_color": "#cf3030", "hover_color": "#8a1c1c"})
        else: del_kw.update({"bg": "red", "fg": "white"})
        self.del_chat_btn = btn_cls(self.sidebar, **del_kw)
        self.del_chat_btn.pack(pady=(5, 10), padx=10)

        # --- TABVIEW ---
        if HAS_CTK:
            self.tab_view = ctk.CTkTabview(self)
            self.tab_view.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
            self.tab_chat = self.tab_view.add("Chat")
            self.tab_files = self.tab_view.add("Files")
            self.tab_chat.grid_columnconfigure(0, weight=1)
            self.tab_chat.grid_rowconfigure(0, weight=1)
        else:
            self.tab_view = ttk.Notebook(self)
            self.tab_view.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
            self.tab_chat = tk.Frame(self.tab_view, bg="#333")
            self.tab_files = tk.Frame(self.tab_view, bg="#333")
            self.tab_view.add(self.tab_chat, text="Chat")
            self.tab_view.add(self.tab_files, text="Files")
            self.tab_chat.columnconfigure(0, weight=1)
            self.tab_chat.rowconfigure(0, weight=1)

        # --- CHAT AREA ---
        if HAS_CTK:
            self.chat_box = ctk.CTkTextbox(self.tab_chat, wrap="word", fg_color="#2b2b2b")
        else:
            self.chat_box = tk.Text(self.tab_chat, bg="#2b2b2b", fg="white", wrap="word", borderwidth=0)
        
        self.chat_box.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.chat_box.configure(state="disabled")

        # --- FILES AREA ---
        lbl_file = lbl_cls(self.tab_files, text="Context Files / Images:")
        if not HAS_CTK: lbl_file.config(fg="white", bg="#333")
        lbl_file.pack(pady=10)

        self.file_list = tk.Listbox(self.tab_files, bg="#2b2b2b", fg="white", borderwidth=0)
        self.file_list.pack(fill="both", expand=True, padx=10, pady=5)

        self.upload_btn = btn_cls(self.tab_files, text="Add File / Image", command=self.upload_file)
        self.upload_btn.pack(pady=10)

        clr_btn_kw = {"text": "Clear Files", "command": self.clear_files}
        if HAS_CTK: clr_btn_kw["fg_color"] = "red"
        else: clr_btn_kw["bg"] = "#800"
        self.clear_files_btn = btn_cls(self.tab_files, **clr_btn_kw)
        self.clear_files_btn.pack(pady=5)
        
        self.attached_files = []

        # --- INPUT AREA ---
        self.input_frame = ctk.CTkFrame(self, height=50) if HAS_CTK else tk.Frame(self, bg="#333")
        self.input_frame.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        if HAS_CTK:
            self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="Type a message...")
        else:
            self.entry = tk.Entry(self.input_frame, bg="#444", fg="white")
            
        self.entry.pack(side="left", fill="both", expand=True, padx=(5, 10), pady=5)
        self.entry.bind("<Return>", self.send)
        
        self.logic_var = tk.BooleanVar(value=False)
        if HAS_CTK:
            self.logic_chk = ctk.CTkCheckBox(self.input_frame, text="Force Logic", variable=self.logic_var, width=80)
        else:
            self.logic_chk = tk.Checkbutton(self.input_frame, text="Force Logic", variable=self.logic_var, bg="#333", fg="white", selectcolor="#444")
        self.logic_chk.pack(side="right", padx=5)

        stop_kw = {"text": "STOP", "command": self.stop_gen, "width": 60}
        if HAS_CTK: stop_kw.update({"fg_color": "#cf3030", "hover_color": "#8a1c1c"})
        else: stop_kw.update({"bg": "red", "fg": "white"})
        self.stop_btn = btn_cls(self.input_frame, **stop_kw)
        self.stop_btn.pack(side="right", padx=5)

        self.send_btn = btn_cls(self.input_frame, text="Send", command=self.send, width=80)
        self.send_btn.pack(side="right", padx=5)

        # --- STATUS BAR ---
        self.status = lbl_cls(self, text="Ready | Ollama Link: http://localhost:11434")
        if HAS_CTK: self.status.configure(text_color="gray")
        else: self.status.config(fg="gray", bg="#333")
        self.status.grid(row=2, column=1, sticky="w", padx=10, pady=(0, 5))

        self.refresh_history_ui()

    def refresh_history_ui(self):
        self.history_list.delete(0, "end")
        for f in self.backend.get_chat_list(): self.history_list.insert("end", f)

    def load_selected_chat(self, event):
        sel = self.history_list.curselection()
        if not sel: return
        filename = self.history_list.get(sel[0])
        history = self.backend.load_chat_history(filename)
        
        self.chat_box.configure(state="normal")
        self.chat_box.delete("1.0", "end")
        for msg in history:
            role = "You" if msg["role"] == "user" else "AI"
            content = msg.get("content", "")
            if "images" in msg: content += " [Image Attached]"
            self.chat_box.insert("end", f"\n\n[{role}]: {content}")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def start_new_chat(self):
        self.backend.new_chat()
        self.clear_files() # FIX: Files now clear on new chat
        self.chat_box.configure(state="normal")
        self.chat_box.delete("1.0", "end")
        self.chat_box.insert("end", "[System]: New session started.")
        self.chat_box.configure(state="disabled")
        self.refresh_history_ui()

    def delete_selected_chat(self):
        sel = self.history_list.curselection()
        if not sel: 
            messagebox.showinfo("Info", "Please select a chat to delete.")
            return
        
        filename = self.history_list.get(sel[0])
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete {filename}?"):
            if self.backend.delete_chat(filename):
                self.refresh_history_ui()
                if filename.replace(".json", "") == self.backend.current_chat_id:
                    self.start_new_chat()
            else:
                messagebox.showerror("Error", "Could not delete file.")

    def upload_file(self):
        path = filedialog.askopenfilename()
        if path: 
            self.attached_files.append(path)
            self.file_list.insert("end", os.path.basename(path))

    def clear_files(self):
        self.attached_files = []
        self.file_list.delete(0, "end")

    def stop_gen(self):
        self.backend.stop_generation()
        self.status.configure(text="Stopping...")

    def send(self, e=None):
        msg = self.entry.get()
        if not msg: return
        self.entry.delete(0, "end")
        
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", f"\n\n[You]: {msg}")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")
        
        # FIX: Files are made ephemeral here
        # We take a snapshot of current files to send to the thread
        files_snapshot = list(self.attached_files)
        
        # We clear the UI and memory immediately so they don't stick around
        self.clear_files()
        
        threading.Thread(target=self.run_ai, args=(msg, files_snapshot), daemon=True).start()

    # [VERIFIED] UI Feedback with Tags
    def callback_handler(self, type, data):
        self.chat_box.configure(state="normal")
        
        # Configure styles if they don't exist
        try:
            self.chat_box.tag_config("ai_header", foreground="#58a6ff", font=("Arial", 10, "bold"))
            self.chat_box.tag_config("system_msg", foreground="#ff7b72")
        except: pass 

        if type == "start_stream":
            self.chat_box.insert("end", "\n\n[AI]: ", "ai_header")
        elif type == "stream":
            self.chat_box.insert("end", data)
            self.chat_box.see("end")
        elif type == "status":
            self.status.configure(text=data)
        elif type == "approval_request":
            # System alerts now stand out in red
            self.chat_box.insert("end", f"\n\n[SYSTEM]: Requesting permission for: {data}", "system_msg")
            if messagebox.askyesno("Security Alert", f"The AI wants to run this command:\n\n{data}\n\nAllow it?"):
                res = self.backend.execute_command(data)
                self.chat_box.insert("end", f"\n[RESULT]: {res}")
        
        self.chat_box.configure(state="disabled")

    def run_ai(self, msg, files_snapshot):
        self.after(0, self.callback_handler, "start_stream", None)
        
        def thread_safe_callback(t, d):
            self.after(0, self.callback_handler, t, d)

        res = self.backend.generate(
            msg, 
            attached_files=files_snapshot, # Pass the snapshot
            force_logic=self.logic_var.get(), 
            callback=thread_safe_callback
        )
        
        self.after(0, self.status.configure, {"text": "Idle"})
        self.after(0, self.refresh_history_ui)

if __name__ == "__main__":
    app = App(AIBackend())
    app.mainloop()
