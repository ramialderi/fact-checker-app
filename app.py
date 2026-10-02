import streamlit as st
from streamlit_mic_recorder import mic_recorder
from google import genai
from google.genai import types
from tavily import TavilyClient

st.set_page_config(page_title="مدقق الكلام الذكي - Gemini", page_icon="🎙️", layout="centered")

st.title("🎙️ مدقق الكلام الفوري (Gemini + Tavily)")
st.write("تحدث بالمعلومة، وسيقوم الذكاء الاصطناعي بالتحقق منها مجاناً.")

# قراءة المفاتيح التلقائية من Secrets
gemini_key = st.secrets.get("GEMINI_API_KEY", "")
tavily_key = st.secrets.get("TAVILY_API_KEY", "")

if not gemini_key or not tavily_key:
    with st.expander("🔑 أدخل المفاتيح يدوياً (إذا لم تضفها في Secrets)"):
        gemini_key = st.text_input("Gemini API Key", value=gemini_key, type="password")
        tavily_key = st.text_input("Tavily API Key", value=tavily_key, type="password")

st.divider()

# مسجل الصوت المباشر للجوال
audio = mic_recorder(
    start_prompt="🔴 اضغط للبدء والتحدث",
    stop_prompt="⏹️ اضغط للإيقاف والتحقق",
    key='recorder'
)

if audio and gemini_key and tavily_key:
    # تهيئة العملاء
    ai_client = genai.Client(api_key=gemini_key)
    tavily_client = TavilyClient(api_key=tavily_key)

    # تشغيل الصوت المباشر في الصفحة مع تحديد الترميز الصحيح
    st.audio(audio['bytes'], format='audio/wav')

    try:
        with st.spinner("⏳ جاري تفريغ الصوت واستخراج النص عبر Gemini..."):
            # إرسال بيانات الصوت مباشرة إلى النموذج في الذاكرة لتفادي مشاكل الحفظ الصامت
            stt_response = ai_client.models.generate_content(
                model='gemini-1.5-flash',
                contents=[
                    types.Part.from_bytes(
                        data=audio['bytes'],
                        mime_type='audio/wav',
                    ),
                    "فرّغ هذا المقطع الصوتي بدقة إلى نص مكتوب باللغة العربية فقط دون أي تفسير أو زيادة."
                ]
            )
            
            text = stt_response.text.strip()
            st.info(f"🗣️ **النص المسموع:** {text}")

        with st.spinner("🔍 جاري البحث والتحقق من صحة الكلام عبر Tavily..."):
            # البحث عن الأدلة عبر الإنترنت
            search_results = tavily_client.search(query=text, search_depth="basic", max_results=3)
            context = "\n".join([f"- {r['content']}" for r in search_results.get('results', [])])

            prompt = f"""
            أنت مدقق حقائق صارم.
            الكلام المستخرج من الصوت: "{text}"
            نتائج البحث المباشر:
            {context}

            حدد حتماً واحدة من النتائج التالية فقط دون أي إضافات أو مقدمات أو نقاط:
            1. معلومة صحيحة
            2. معلومة كاذبة
            3. معلومة غير موثقة
            """

            # تقييم النص باستخدام Gemini
            verdict_response = ai_client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt
            )
            
            verdict = verdict_response.text.strip()

        st.divider()
        if "صحيحة" in verdict:
            st.success(f"✅ **النتيجة: {verdict}**")
        elif "كاذبة" in verdict:
            st.error(f"❌ **النتيجة: {verdict}**")
        else:
            st.warning(f"⚠️ **النتيجة: {verdict}**")

    except Exception as e:
        st.error(f"حدث خطأ أثناء المعالجة: {str(e)}")
