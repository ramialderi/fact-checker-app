import streamlit as st
from streamlit_mic_recorder import mic_recorder
from google import genai
from google.genai import types
from tavily import TavilyClient

st.set_page_config(page_title="مدقق الكلام الذكي - Gemini", page_icon="🎙️", layout="centered")

st.title("🎙️ مدقق الكلام الفوري (Gemini + Tavily)")
st.write("تحدث بالمعلومة، وسيقوم الذكاء الاصطناعي بالتحقق منها.")

gemini_key = st.secrets.get("GEMINI_API_KEY", "")
tavily_key = st.secrets.get("TAVILY_API_KEY", "")

if not gemini_key or not tavily_key:
    with st.expander("🔑 أدخل المفاتيح يدوياً (إذا لم تضفها في Secrets)"):
        gemini_key = st.text_input("Gemini API Key", value=gemini_key, type="password")
        tavily_key = st.text_input("Tavily API Key", value=tavily_key, type="password")

# قائمة النماذج: يجرّب الأول ثم ينتقل للتالي إذا لم يكن متاحاً
# يمكنك فرض نموذج معين بإضافة GEMINI_MODEL في Secrets
MODELS = [m for m in [
    st.secrets.get("GEMINI_MODEL", ""),
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
] if m]


def ask_gemini(client, contents):
    last_error = None
    for model in MODELS:
        try:
            return client.models.generate_content(model=model, contents=contents).text.strip()
        except Exception as e:
            last_error = e
            if "404" in str(e) or "NOT_FOUND" in str(e):
                continue  # النموذج غير متاح، جرّب التالي
            raise
    raise last_error


st.divider()

audio = mic_recorder(
    start_prompt="🔴 اضغط للبدء والتحدث",
    stop_prompt="⏹️ اضغط للإيقاف والتحقق",
    format="wav",          # مهم: صيغة wav تعمل على كل الأجهزة
    key="recorder",
)

if audio and gemini_key and tavily_key:
    ai_client = genai.Client(api_key=gemini_key)
    tavily_client = TavilyClient(api_key=tavily_key)

    st.audio(audio["bytes"], format="audio/wav")

    if len(audio["bytes"]) < 5000:
        st.warning("⚠️ التسجيل فارغ أو قصير جداً. تأكد من السماح للمتصفح باستخدام المايكروفون ثم أعد المحاولة.")
        st.stop()

    try:
        with st.spinner("⏳ جاري تفريغ الصوت..."):
            text = ask_gemini(ai_client, [
                types.Part.from_bytes(data=audio["bytes"], mime_type="audio/wav"),
                "فرّغ هذا المقطع الصوتي بدقة إلى نص مكتوب باللغة العربية فقط. إذا لم تجد كلاماً واضحاً اكتب 'صوت غير واضح'.",
            ])

        if not text or "غير واضح" in text:
            st.warning("⚠️ لم يتم التقاط صوت واضح، تحدث بقرب من المايكروفون وأعد المحاولة.")
        else:
            st.info(f"🗣️ **النص المسموع:** {text}")

            with st.spinner("🔍 جاري البحث والتحقق..."):
                results = tavily_client.search(query=text, search_depth="basic", max_results=3)
                context = "\n".join(f"- {r['content']}" for r in results.get("results", []))

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
                verdict = ask_gemini(ai_client, prompt)

            st.divider()
            if "غير موثقة" in verdict:
                st.warning(f"⚠️ **النتيجة: {verdict}**")
            elif "كاذبة" in verdict:
                st.error(f"❌ **النتيجة: {verdict}**")
            elif "صحيحة" in verdict:
                st.success(f"✅ **النتيجة: {verdict}**")
            else:
                st.warning(f"⚠️ **النتيجة: {verdict}**")

    except Exception as e:
        st.error(f"حدث خطأ أثناء المعالجة: {e}")
