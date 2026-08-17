"""One-off script to generate demo_data/row_01.txt .. row_11.txt with realistic
mixed Hindi/English content plus <BITMAP>...</BITMAP> placeholders, matching the
real-world Notepad export format described in the spec."""
import os

DEMO_DIR = os.path.dirname(os.path.abspath(__file__))

DOCS = {
    "row_01.txt": (
        "राष्ट्रीय मंदिर के पास इलाके में भीषण आग <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "A major fire occurred near the temple.\n"
        "दर्शनार्थियों की भीड़ में अचानक मौत <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "The crowd suddenly faced a tragedy.\n"
        "7 श्रद्धालुओं की मौत, 12 से अधिक लोग घायल <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "Seven people died and many were injured.\n"
        "भारत ने India के साथ नई बातचीत शुरू की <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "India started a new discussion.\n"
        "<BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
    ),
    "row_02.txt": (
        "राष्ट्रीय मंदिर के पास इलाके में भीषण आग <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "A major fire occurred near the temple.\n"
        "7 श्रद्धालुओं की मौत, 12 से अधिक लोग घायल <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "Seven people died and many were injured.\n"
        "भारत ने India के साथ नई बातचीत शुरू की <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "India started a new discussion.\n"
    ),
    "row_03.txt": (
        "कोलकाता में सड़क पर बड़ा हादसा <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "A major accident occurred on the road in Kolkata.\n"
        "पश्चिम बंगाल सरकार ने राहत कोष जारी किया <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "The West Bengal government released a relief fund.\n"
    ),
    "row_04.txt": (
        "अभी-अभी: मुख्यमंत्री ने बड़ी घोषणा की <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "Just in: the Chief Minister made a major announcement.\n"
        "देशभर में सुरक्षा व्यवस्था कड़ी की गई <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "Security has been tightened nationwide.\n"
    ),
    "row_05.txt": (
        "बिहार में बाढ़ से हजारों लोग प्रभावित <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "Thousands of people affected by floods in Bihar.\n"
        "प्रशासन ने राहत शिविर लगाए <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "The administration set up relief camps.\n"
    ),
    "row_06.txt": (
        "झारखंड में खनन क्षेत्र में नई नीति लागू <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "A new policy implemented in Jharkhand's mining sector.\n"
        "रांची में सड़क निर्माण कार्य शुरू <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "Road construction work began in Ranchi.\n"
    ),
    "row_07.txt": (
        "विशेषज्ञों ने चुनावी नतीजों पर चर्चा की <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "Experts discussed the election results in detail.\n"
        "यह विश्लेषण आगे की रणनीति के लिए महत्वपूर्ण है <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "This analysis is important for future strategy.\n"
    ),
    "row_08.txt": (
        "नई फिल्म जल्द रिलीज होने वाली है <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "A new movie is going to be released soon.\n"
        "अभिनेता ने सोशल मीडिया पर जानकारी दी <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "The actor shared the information on social media.\n"
    ),
    "row_09.txt": (
        "पूरी स्क्रीन ब्रेकिंग: बड़ा फैसला सुनाया गया <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "Full screen breaking: a major decision has been announced.\n"
        "सभी चैनलों पर लाइव प्रसारण जारी <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "Live broadcast continues on all channels.\n"
    ),
    "row_10.txt": (
        "अपर बैंड: शेयर बाजार में उतार-चढ़ाव जारी <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "Upper band: fluctuations continue in the stock market.\n"
        "सोने-चांदी के दाम में मामूली बदलाव <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "Minor change in gold and silver prices.\n"
    ),
    "row_11.txt": (
        "यह पंक्ति अभी किसी श्रेणी से जुड़ी नहीं है <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
        "This line is not yet assigned to any category.\n"
    ),
}


def main():
    os.makedirs(DEMO_DIR, exist_ok=True)
    for filename, content in DOCS.items():
        path = os.path.join(DEMO_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Created {path}")


if __name__ == "__main__":
    main()
