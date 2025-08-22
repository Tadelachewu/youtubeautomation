import os
import re
import time
import json
import requests
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from gtts import gTTS
from PIL import Image, ImageFile
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    TextClip,
    ImageClip,
    ColorClip
)

# Enable PIL to load truncated images
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Load environment variables
load_dotenv()

# -----------------------------
# YouTube Uploader (async)
# -----------------------------
from youtube_uploader import upload_video
from youtube_batch_upload import batch_upload

# -----------------------------
# Image Generation
# -----------------------------
def pollinations_generate_image(prompt, output_path, retries=3, delay=5):
    for attempt in range(retries):
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            base, ext = os.path.splitext(output_path.name)
            safe_base = re.sub(r'[^a-zA-Z0-9_]', '_', base)[:120]
            output_path = output_path.parent / f"{safe_base}{ext}"

            if output_path.exists():
                print(f"⚡ Using cached image: {output_path}")
                return str(output_path)

            url = f"https://image.pollinations.ai/prompt/{prompt}"
            response = requests.get(url, timeout=60)  # increase timeout
            response.raise_for_status()
            
            with open(output_path, "wb") as f:
                f.write(response.content)
            
            img = Image.open(output_path)
            img.verify()
            print(f"✅ Generated image: {output_path}")
            return str(output_path)

        except Exception as e:
            print(f"❌ Pollinations attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                print("⚠️ Using placeholder image instead")
                return str(Path("assets/placeholder_bg.jpeg"))

def generate_image(prompt, output_path, image_source_choice):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if image_source_choice == "2":
        return pollinations_generate_image(prompt, output_path)
    else:
        # Freepik AI placeholder (not implemented)
        return None

# -----------------------------
# Helper functions
# -----------------------------
def clean_script_text(script):
    """Clean text for voiceover/subtitles (remove *, brackets, extra whitespace)"""
    script = script.replace('*', '')
    script = re.sub(r'\[[^\]]*\]', '', script)
    script = re.sub(r'\([^\)]*\)', '', script)
    script = re.sub(r'\s+', ' ', script).strip()
    return script

def parse_script(script):
    """Parse script with timestamps into scenes"""
    scenes = []
    pattern = r'\[(\d+:\d{2})-(\d+:\d{2})\](.*?)(?=\[|$)'
    for match in re.finditer(pattern, script, re.DOTALL):
        start, end, content = match.groups()
        start_sec = sum(x * int(t) for x, t in zip([60, 1], start.split(':')))
        end_sec = sum(x * int(t) for x, t in zip([60, 1], end.split(':')))
        duration = max(end_sec - start_sec, 1)  # at least 1 sec
        text = re.sub(r'\([^)]*\)', '', content).replace('*', '').strip()
        text = re.sub(r'\s+', ' ', text)
        visuals = re.findall(r'\(([^)]+)\)', content)
        scenes.append({
            'start': start_sec,
            'end': end_sec,
            'duration': duration,
            'text': text,
            'visuals': visuals[0] if visuals else 'technology background'
        })
    print(f"✅ Parsed {len(scenes)} scenes")
    return scenes

# -----------------------------
# Video Creator Class
# -----------------------------
class VideoCreator:
    def __init__(self):
        self.temp_dir = Path("temp")
        self.output_dir = Path("output")
        self.assets_dir = Path("assets")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

        placeholder = self.assets_dir / "placeholder_bg.jpeg"
        if not placeholder.exists():
            self.create_placeholder_image(placeholder)

    def create_placeholder_image(self, path):
        img = Image.new('RGB', (1280, 720), color=(40, 40, 40))
        img.save(path)
        print(f"✅ Created placeholder image at {path}")

    def safe_filename(self, text, ext=".jpeg"):
        safe = re.sub(r'[^a-zA-Z0-9_]', '_', text)[:150]
        return self.temp_dir / f"{safe}{ext}"

    def generate_script(self, topic):
        print(f"📝 Requesting script for topic: {topic}")
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"
            headers = {'Content-Type': 'application/json'}
            payload = {
                "contents": [{
                    "parts": [{
                        "text": f"""Create a highly engaging 60-second YouTube Shorts script about: {topic}

CRITICAL REQUIREMENTS:
- HOOK FIRST: Start with an irresistible 3-second hook that stops the scroll
- FAST PACED: Maximum viewer retention - every second must deliver value
- VISUAL FIRST: Design for vertical video (9:16 aspect ratio)
- EMOTIONAL IMPACT: Create curiosity, surprise, or "aha" moments

SCRIPT STRUCTURE:
[0:00-0:03] - HOOK: Start with shocking fact, intriguing question, or visual spectacle
[0:03-0:15] - PROBLEM: Setup the pain point or curiosity gap
[0:15-0:45] - SOLUTION: Deliver the main value with clear, actionable insights
[0:45-0:55] - PAYOFF: Big reveal or satisfying conclusion
[0:55-1:00] - CTA: Natural call-to-action that doesn't feel salesy

CONTENT GUIDELINES:
- Write for Gen Z/TikTok attention spans
- Include specific visual directions in (parentheses) for each scene
- Add text overlay suggestions [in brackets] for key points
- Use conversational, energetic language
- Include 1-2 unexpected twists or revelations
- End with a thought-provoking question or engaging CTA

EXAMPLE FORMAT:
[0:00-0:03] (Extreme close-up of surprising object) "You won't believe what this actually does..."
[Text overlay: "WRONG YOUR WHOLE LIFE?"]

Generate the most viral-worthy version possible that maximizes shareability and completion rates."""
                    }]
                }]
            }
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
            response.raise_for_status()
            data = response.json()
            script = data["candidates"][0]["content"]["parts"][0]["text"]
            print("✅ Script received")
            return script
        except Exception as e:
            print(f"❌ Gemini API Error: {e}")
            return None

    def create_voiceover(self, text, filename="voiceover.mp3"):
        voice_path = self.temp_dir / filename
        try:
            print("🔊 Generating voiceover...")
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(str(voice_path))
            print(f"✅ Voiceover saved at {voice_path}")
            return str(voice_path)
        except Exception as e:
            print(f"❌ Voiceover error: {e}")
            return None

    def generate_ai_image(self, prompt, image_source_choice):
        img_path = self.safe_filename(prompt)
        if img_path.exists():
            return str(img_path)
        generated_path = generate_image(prompt, str(img_path), image_source_choice)
        if generated_path and Path(generated_path).exists():
            return generated_path
        fallback = self.assets_dir / "placeholder_bg.jpeg"
        return str(fallback)

    def create_visual_clip(self, visual_desc, duration, size=(1280, 720), image_source_choice="1"):
        prompt = re.sub(r'^[Vv]isuals?:\s*', '', visual_desc.strip())[:200].strip()
        if not prompt or any(k in prompt.lower() for k in ['music', 'audio', 'sound']):
            prompt = "technology abstract background"

        img_path = self.generate_ai_image(prompt, image_source_choice)
        try:
            clip = ImageClip(img_path).set_duration(duration).resize(newsize=size)
            return clip
        except:
            return ColorClip(size, color=(30, 30, 60), duration=duration)

    def create_video(self, topic):
        print(f"\n🚀 Creating video: {topic}")
        image_source_choice = input("Select image source (1: Freepik, 2: Pollinations): ").strip()
        script = self.generate_script(topic)
        if not script:
            print("❌ Script generation failed")
            return None

        cleaned_script = clean_script_text(script)
        voiceover_path = self.create_voiceover(cleaned_script)
        if not voiceover_path:
            print("❌ Voiceover creation failed")
            return None

        audio_clip = AudioFileClip(voiceover_path)
        if audio_clip.duration < 1:
            print("❌ Audio too short")
            return None

        scenes = parse_script(script)
        if not scenes:
            print("❌ No scenes parsed")
            return None

        # ✅ Generate visual clips
        visual_clips = []
        for i, scene in enumerate(scenes):
            clip = self.create_visual_clip(
                scene['visuals'],
                scene['duration'],
                image_source_choice=image_source_choice
            ).set_start(scene['start'])

            # ✅ If it's the last scene → extend to end of audio
            if i == len(scenes) - 1:
                clip = clip.set_duration(audio_clip.duration - scene['start'])

            visual_clips.append(clip)

        # ✅ Background covers full audio duration
        bg_clip = CompositeVideoClip(visual_clips, size=(1280, 720)).set_duration(audio_clip.duration)

        # Subtitles - Improved to handle all scenes properly
        text_clips = []
        for scene in scenes:
            # Skip empty text
            if not scene['text'].strip():
                continue
                
            # Create text clip with better styling for visibility
            try:
                txt_clip = TextClip(
                    scene['text'], 
                    fontsize=42, 
                    color='white', 
                    font='Arial-Bold',
                    stroke_color='black', 
                    stroke_width=2, 
                    size=(1000, None),
                    method='caption', 
                    align='center',
                    bg_color='rgba(0,0,0,0.5)',
                    transparent=True
                ).set_position(('center', 550)).set_start(scene['start']).set_duration(scene['duration'])
                text_clips.append(txt_clip)
            except Exception as e:
                print(f"⚠️ Could not create subtitle for scene: {e}")

        # Create final video with all elements
        final_clip = CompositeVideoClip([bg_clip] + text_clips)
        final_clip = final_clip.set_audio(audio_clip).set_duration(audio_clip.duration)

        output_path = self.output_dir / f"{re.sub(r'[^a-zA-Z0-9_]', '', topic.replace(' ', '_'))}.mp4"
        
        # Write video file with optimized settings
        final_clip.write_videofile(
            str(output_path), 
            codec="libx264", 
            audio_codec="aac", 
            fps=24, 
            threads=4,
            preset='fast',
            ffmpeg_params=['-crf', '23']
        )

        print(f"\n🎉 Video created successfully: {output_path}")

        # Upload to YouTube
        try:
            print("📤 Uploading to YouTube...")
            # async def upload(): 
            #     await upload_video(str(output_path), topic, f"Automated video about {topic}", ["AI","Automation","Tech"])
            # asyncio.run(upload())
            asyncio.run(batch_upload()) # print("✅ Upload initiated")
        except Exception as e:
            print(f"⚠️ YouTube upload failed: {e}")

        return str(output_path)


# -----------------------------
# Main Runner
# -----------------------------
if __name__ == "__main__":
    creator = VideoCreator()
    result = creator.create_video("docker with detailed explanations with code explanations step by step with real simulation")
    
    if not result:
        print("\n❌ Video creation failed.")
    else:
        print("\n✅ Video created successfully!")