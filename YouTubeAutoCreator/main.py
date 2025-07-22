import os
import re
import json
import base64
import requests
from dotenv import load_dotenv
from gtts import gTTS
from moviepy import (
    AudioFileClip, CompositeVideoClip, TextClip,
    ImageClip, ColorClip
)

load_dotenv()

class VideoCreator:
    def __init__(self):
        self.temp_dir = "temp"
        self.output_dir = "outputs"
        self.assets_dir = "assets"
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.stability_api_key = os.getenv("STABILITY_API_KEY")

        print("🔧 Initializing directories...")
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.assets_dir, exist_ok=True)

    def generate_script(self, topic):
        print(f"📝 Requesting script for topic: {topic}")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{
                "parts": [{
                    "text": f"Create a 1-minute YouTube script about {topic} with scene descriptions. "
                            "Format with timestamps like [0:00-0:05] for each section. "
                            "Include visual descriptions in parentheses."
                }]
            }]
        }

        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
            data = response.json()
            print("✅ Script received.")
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"❌ Gemini API Error: {str(e)}")
            return None

    def create_voiceover(self, text, filename="voiceover.mp3"):
        try:
            print("🔊 Generating voiceover...")
            tts = gTTS(text=text, lang='en')
            voice_path = os.path.join(self.temp_dir, filename)
            tts.save(voice_path)
            print(f"✅ Voiceover saved at {voice_path}")
            return voice_path
        except Exception as e:
            print(f"❌ Voiceover error: {str(e)}")
            return None

    def parse_script(self, script):
        print("🔍 Parsing script...")
        scenes = []
        pattern = r'\[(\d+:\d{2})-(\d+:\d{2})\](.*?)(?=\[|$)'
        for match in re.finditer(pattern, script, re.DOTALL):
            start, end, content = match.groups()
            start_sec = sum(x * int(t) for x, t in zip([60, 1], start.split(':')))
            end_sec = sum(x * int(t) for x, t in zip([60, 1], end.split(':')))
            duration = end_sec - start_sec
            visuals = re.findall(r'\(([^)]+)\)', content)
            scenes.append({
                'text': re.sub(r'\([^)]*\)', '', content).strip(),
                'visuals': visuals[0] if visuals else "",
                'start': start_sec,
                'end': end_sec,
                'duration': duration
            })
        print(f"✅ Parsed {len(scenes)} scenes.")
        return scenes

    def generate_ai_image(self, prompt, filename):
        print(f"🎨 Generating SD3 image for: {prompt}")
        if not self.stability_api_key:
            print("❌ STABILITY_API_KEY not found in .env")
            return None

        url = "https://api.stability.ai/v2beta/stable-image/generate/sd3"
        headers = {
            "authorization": f"Bearer {self.stability_api_key}",
            "accept": "image/*"
        }
        files = {"none": ''}
        data = {
            "prompt": prompt,
            "output_format": "jpeg"
        }

        try:
            response = requests.post(url, headers=headers, files=files, data=data)
            if response.status_code == 200:
                with open(filename, "wb") as f:
                    f.write(response.content)
                print(f"✅ Image saved: {filename}")
                return filename
            else:
                print(f"❌ SD3 API Error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"❌ Exception during image generation: {e}")
            return None

    
    def create_visual_clip(self, visual_desc, duration, size=(1280, 720)):
        prompt = re.sub(r'^[Vv]isuals?:\s*', '', visual_desc.strip())
        prompt = re.sub(r'Upbeat.*', '', prompt)
        prompt = prompt[:200].strip()  # trim and strip whitespace

        # Check if prompt is valid for image generation
        if not prompt or any(keyword in prompt.lower() for keyword in ['music', 'audio', 'sound', 'upbeat']):
            print(f"⚠️ Skipping AI image generation for non-visual or empty prompt: '{prompt}'")
            return ColorClip(size, color=(30, 30, 30), duration=duration)

        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', prompt)
        img_path = os.path.join(self.temp_dir, f"{safe_name}.jpeg")

        if not os.path.exists(img_path):
            print(f"🤖 Generating visual: {prompt}")
            generated = self.generate_ai_image(prompt, img_path)
            if not generated:
                print(f"⚠️ Failed to generate image. Using fallback.")
                return ColorClip(size, color=(30, 30, 30), duration=duration)

        try:
            clip = ImageClip(img_path).set_duration(duration).resize(newsize=size)
            return clip
        except Exception as e:
            print(f"❌ Error creating ImageClip: {e}")
            return ColorClip(size, color=(60, 0, 0), duration=duration)

    def create_video(self, topic):
        try:
            print("🎬 Starting video creation...")
            script = self.generate_script(topic)
            if not script:
                raise Exception("Script generation failed")

            print("📢 Creating voiceover...")
            voiceover_path = self.create_voiceover(script)
            if not voiceover_path:
                raise Exception("Voiceover generation failed")

            audio_clip = AudioFileClip(voiceover_path)
            total_duration = audio_clip.duration

            scenes = self.parse_script(script)

            print("📷 Generating visual clips...")
            visual_clips = []
            for scene in scenes:
                print(f"🖼️ Visual: {scene['visuals']}")
                clip = self.create_visual_clip(scene['visuals'], scene['duration'])
                clip = clip.set_start(scene['start'])  # set_start AFTER set_duration (already done inside create_visual_clip)
                visual_clips.append(clip)

            bg_clip = CompositeVideoClip(visual_clips, size=(1280, 720)).set_duration(total_duration)

            print("📝 Adding subtitles...")
            text_clips = []
            for scene in scenes:
                try:
                    txt_clip = TextClip(
                        scene['text'],
                        fontsize=32,
                        color='white',
                        size=(int(bg_clip.w * 0.9), None),
                        method='caption',
                        align='center'
                    ).set_position(('center', 'bottom')).set_start(scene['start']).set_duration(scene['duration'])
                    text_clips.append(txt_clip)
                except Exception as e:
                    print(f"⚠️ TextClip error: {e}")

            final_clip = CompositeVideoClip([bg_clip] + text_clips).set_audio(audio_clip)

            output_path = os.path.join(
                self.output_dir,
                f"{re.sub(r'[^a-zA-Z0-9_]', '', topic.replace(' ', '_'))}.mp4"
            )
            print("🚀 Rendering video...")
            final_clip.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                fps=24,
                threads=4,
                bitrate="5000k"
            )
            print(f"✅ Final video at: {output_path}")
            return output_path

        except Exception as e:
            print(f"❌ Video creation failed: {str(e)}")
            return None


# Entry point
if __name__ == "__main__":
    creator = VideoCreator()
    creator.create_video("How AI is transforming Ethiopia")
