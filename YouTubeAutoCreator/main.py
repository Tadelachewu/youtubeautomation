import os
import requests
import json
import re
from moviepy import *
from gtts import gTTS
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

class VideoCreator:
    def __init__(self):
        self.temp_dir = "temp"
        self.output_dir = "outputs"
        self.assets_dir = "assets"
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.assets_dir, exist_ok=True)

    def generate_script(self, topic):
        """Generate video script using Gemini API"""
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
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"❌ Gemini API Error: {str(e)}")
            return None

    def create_voiceover(self, text, filename="voiceover.mp3"):
        """Generate voiceover using gTTS"""
        tts = gTTS(text=text, lang='en')
        voice_path = os.path.join(self.temp_dir, filename)
        tts.save(voice_path)
        return voice_path

    def get_background_clip(self, duration=60):
        """Create a background clip with proper duration"""
        return ColorClip((1280, 720), color=(30, 30, 30)).set_duration(duration)

    def parse_script(self, script):
        """Improved script parser with timestamp handling"""
        scenes = []
        pattern = r'\[(\d+:\d{2})-(\d+:\d{2})\](.*?)(?=\[|$)'
        
        for match in re.finditer(pattern, script, re.DOTALL):
            start, end, content = match.groups()
            
            # Convert timestamps to seconds
            start_sec = sum(x * int(t) for x, t in zip([60, 1], start.split(':')))
            end_sec = sum(x * int(t) for x, t in zip([60, 1], end.split(':')))
            duration = end_sec - start_sec
            
            # Extract visual descriptions
            visuals = re.findall(r'\(([^)]+)\)', content)
            
            scenes.append({
                'text': re.sub(r'\([^)]*\)', '', content).strip(),
                'visuals': visuals[0] if visuals else "",
                'start': start_sec,
                'end': end_sec,
                'duration': duration
            })
            
        return scenes

    def create_video(self, topic):
        """Full video creation pipeline"""
        try:
            print("🔹 Generating script...")
            script = self.generate_script(topic)
            if not script:
                raise Exception("Script generation failed")
            
            print("Generated Script:\n", script)
            
            print("🔹 Creating voiceover...")
            voiceover = self.create_voiceover(script)
            audio_clip = AudioFileClip(voiceover)
            total_duration = audio_clip.duration
            
            print("🔹 Preparing visuals...")
            bg_clip = self.get_background_clip(total_duration)
            
            print("🔹 Editing video...")
            # Create text clips with improved parsing
            scenes = self.parse_script(script)
            text_clips = []
            
            for scene in scenes:
                txt_clip = TextClip(
                    scene['text'],
                    fontsize=32,
                    color='white',
                    font="Arial-Bold",
                    size=(bg_clip.w * 0.9, None),
                    method='caption',
                    align='center'
                ).set_position(('center', 'bottom')).set_duration(scene['duration'])
                text_clips.append(txt_clip)
            
            final_clip = CompositeVideoClip([bg_clip] + text_clips)
            final_clip = final_clip.set_audio(audio_clip)
            
            output_path = os.path.join(self.output_dir, f"{topic.replace(' ', '_')}.mp4")
            
            print("🔹 Rendering final video...")
            final_clip.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                fps=24,
                threads=4,
                bitrate="5000k"
            )
            
            print(f"✅ Video created: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return None

if __name__ == "__main__":
    creator = VideoCreator()
    creator.create_video("How AI is transforming Ethiopia")