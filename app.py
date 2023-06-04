from flask import Flask,jsonify,Response,render_template,request
import requests
from bs4 import BeautifulSoup
import json
from sumy.summarizers.luhn import LuhnSummarizer
from sumy.nlp.tokenizers import Tokenizer
from sumy.parsers.plaintext import PlaintextParser
from nltk.tokenize import sent_tokenize
import spacy
import pytextrank
from sumy.summarizers.lex_rank import LexRankSummarizer
from sumy.summarizers.lsa import LsaSummarizer
import nltk
import sqlite3
from datetime import date
import bcrypt
import schedule
import threading
from datetime import datetime,timedelta
import pytz


con = sqlite3.connect("TrakyaNewsDB.db",check_same_thread=False)
cursor = con.cursor()

nltk.download('punkt')
try:
    nlp = spacy.load("en_core_web_md")
except: # If not present, we download
    spacy.cli.download("en_core_web_md")
    nlp = spacy.load("en_core_web_md")
nlp.add_pipe("textrank")
app = Flask(__name__,template_folder="templates",static_folder="statics")
app.config['JSON_AS_ASCII'] = False

month_dict = {
    "Ocak":"01",
    "Şubat": "02",
    "Mart": "03",
    "Nisan": "04",
    "Mayıs": "05",
    "Haziran": "06",
    "Temmuz": "07",
    "Ağustos": "08",
    "Eylül": "09",
    "Ekim": "10",
    "Kasım": "11",
    "Aralık": "12"
}


#Algorithms
def luhn(metin, cumle_sayisi=3):
    ozet_luhn = LuhnSummarizer()
    parser = PlaintextParser.from_string(metin, Tokenizer("turkish"))
    b = str(metin).split(".")
    ozet = ozet_luhn(parser.document, cumle_sayisi)
    a = ""
    for cumle in ozet:
        a = a + str(cumle)
    return a

def lex_rank(metin, cumle_sayisi=3):
    ozet_lex = LexRankSummarizer()
    parser = PlaintextParser.from_string(metin, Tokenizer("turkish"))
    ozet = ozet_lex(parser.document, cumle_sayisi)
    a = ""
    for cumle in ozet:
        a = a + str(cumle)
    return a

def lsa_summary(metin, cumle_sayisi=3):
    ozet_lsa = LsaSummarizer()
    parser = PlaintextParser.from_string(metin, Tokenizer("turkish"))
    ozet = ozet_lsa(parser.document, cumle_sayisi)
    lsa_summary = ""
    for sentence in ozet:
        lsa_summary += str(sentence)
    return lsa_summary

def all_in_one(metin):
    splitted_sentences = str(metin).split(".")
    a = ""
    for i in splitted_sentences:
        a = a + i

    if len(a) >= 4 and len(a) < 6:
        return lex_rank(lsa_summary(luhn(str(a), len(a) - 1), len(a) - 2), len(a) - 3) + "."
    if len(a) >= 6:
        return textrank(
            lex_rank(lsa_summary(luhn(str(a), len(a) - 1), len(a) - 2), len(a) - 3)) + "."
    else:
        return lex_rank(metin) + "."

def ortayol(metin):

    luhnSet = set(str(luhn(metin)).split("."))
    lsaSet = set(str(lsa_summary(metin)).split("."))
    lexSet = set(str(lex_rank(metin)).split("."))
    textSet = set(str(textrank(metin)).split("."))

    same_sentences = luhnSet.intersection(lsaSet).intersection(lexSet).intersection(textSet)
    if str(same_sentences) == '{"}' or str(same_sentences) == "set()":
        return "Bu metin seçilen algoritma için uygun değil..."
    clipped_str = str(same_sentences).replace("{,", "").replace("{'", "").replace("}", "").replace("{", "").strip(
        "'").strip("',").replace("',", ".").replace("'", "").strip('"')
    if clipped_str == "" or len(clipped_str) < 3:
        return "Bu metin seçilen algoritma için uygun değil..."
    else:
        return clipped_str + "."

def giso(metin):
    splitted_sentences = str(metin).split(".")
    if len(splitted_sentences) >= 5 and len(splitted_sentences) <= 7:
        return str(splitted_sentences[0:2] + splitted_sentences[-1:-3]).replace("[,", "").replace("['", "").replace(
            "]", "").replace("[", "").strip("'").strip("',").replace("',", ".").replace("'", "").strip('"') + "."
    if len(splitted_sentences) >= 8 and len(splitted_sentences) <= 12:
        return str(splitted_sentences[0:3] + splitted_sentences[-1:-4]).replace("[,", "").replace("['", "").replace(
            "]", "").replace("[", "").strip("'").strip("',").replace("',", ".").replace("'", "").strip('"') + "."
    if len(splitted_sentences) >= 13:
        return str(splitted_sentences[0:4] + splitted_sentences[-1:-5]).replace("[,", "").replace("['", "").replace(
            "]", "").replace("[", "").strip("'").strip("',").replace("',", ".").replace("'", "").strip('"') + "."
    else:
        return metin

def textrank(text):

    doc = nlp(text)
    sentences = sent_tokenize(text)
    result = ""
    number = len(sentences)

    if number > 20:
        for sent in doc._.textrank.summary(limit_phrases=40, limit_sentences=5):
            result += str(sent)
    elif number > 40:
        for sent in doc._.textrank.summary(limit_phrases=40, limit_sentences=8):
            result += str(sent)
    elif number > 60:
        for sent in doc._.textrank.summary(limit_phrases=40, limit_sentences=11):
            result += str(sent)
    else:
        for sent in doc._.textrank.summary(limit_phrases=40, limit_sentences=2):
            result += str(sent)
    return result


def saveToDatabase(title, image, text, date, site_name, url_link, type):
    cursor.execute(f"insert into News(title,image,text,date,site_name,url_link,type) values(?,?,?,?,?,?,?)",
                   (title, image, text, date, site_name, url_link, type))
    con.commit()
    id = cursor.execute(f"select news_id from News where url_link = '{url_link}'").fetchone()
    cursor.execute(
        f"insert into Summarizers(new_id,luhn,lexrank,lsa,textrank,giso,ortayol,all_in_one) values (?,?,?,?,?,?,?,?)",
        (id[0], luhn(text), lex_rank(text), lsa_summary(text), textrank(text),
         giso(text), ortayol(text), all_in_one(text)))
    con.commit()




def date_converter(tarih, site):
    if site == "sözcü":
        tarih = str(tarih).replace("-", "").split(" ")
        temp_date = tarih[4] + "-" + month_dict[tarih[3]] + "-" + tarih[2] + " " + tarih[0]
        return temp_date
    if site == "karar":
        tarih = str(tarih).replace("/", " ").split(" ")
        temp_date = tarih[2] + "-" + tarih[1] + "-" + tarih[0] + " " + tarih[3]
        return temp_date
    if site == "trt":
        tarih = str(tarih).replace(", ", "").replace(".", " ").split(" ")
        temp_date = tarih[2] + "-" + tarih[1] + "-" + tarih[0] + " " + tarih[3]
        return temp_date
    if site == "son dakika":
        tarih = str(tarih).replace(".", " ").split(" ")
        temp_date = tarih[2] + "-" + tarih[1] + "-" + tarih[0] + " " + tarih[3]
        return temp_date
    if site == "gerçek gündem":
        tarih = str(tarih).split(" ")
        temp_date = tarih[2] + "-" + month_dict[tarih[1]] + "-" + tarih[0] + " " + tarih[3]
        return temp_date


def makale_cek(url):
    url1 = requests.get(url)
    soup = BeautifulSoup(url1.content, "lxml")
    a = ""
    for p in soup.select('article>p'):
        a = a + p.getText()
    if (a != ""):
        return a

    if a == "":
        for i in soup.select('p:not(:has(*))'):
            a = a + i.getText()

        if (a != ""):
            a = a.strip("""Haberturk.com ekibi olarak Türkiye’de ve dünyada yaşanan ve haber değeri taşıyan her türlü gelişmeyi sizlere en hızlı, en objektif ve en doyurucu şekilde ulaştırmak için çalışıyoruz. Yoğun gündem içerisinde sunduğumuz haberlerimizle ve olaylarla ilgili eleştiri, görüş, yorumlarınız bizler için çok önemli. Fakat karşılıklı saygı ve yasalara uygunluk çerçevesinde oluşturduğumuz yorum platformlarında daha sağlıklı bir tartışma ortamını temin etmek amacıyla ortaya koyduğumuz bazı yorum ve moderasyon kurallarımıza dikkatinizi çekmek istiyoruz.
            Sayfamızda Türkiye Cumhuriyeti kanunlarına ve evrensel insan haklarına aykırı yorumlar onaylanmaz ve silinir. Okurlarımız tarafından yapılan yorumların, (yorum yapan diğer okurlarımıza yönelik yorumlar da dahil olmak üzere) kişilere, ülkelere, topluluklara, sosyal sınıflara ırk, cinsiyet, din, dil başta olmak üzere ayrımcılık unsurları taşıması durumunda yorum editörlerimiz yorumları onaylamayacaktır ve yorumlar silinecektir. Onaylanmayacak ve silinecek yorumlar kategorisinde aşağılama, nefret söylemi, küfür, hakaret, kadın ve çocuk istismarı, hayvanlara yönelik şiddet söylemi içeren yorumlar da yer almaktadır. Suçu ve suçluyu övmek, Türkiye Cumhuriyeti yasalarına göre suçtur. Bu nedenle bu tarz okur yorumları da doğal olarak Haberturk.com yorum sayfalarında yer almayacaktır.
            Ayrıca Haberturk.com yorum sayfalarında Türkiye Cumhuriyeti mahkemelerinde doğruluğu ispat edilemeyecek iddia, itham ve karalama içeren, halkın tamamını veya bir bölümünü kin ve düşmanlığa tahrik eden, provokatif yorumlar da yapılamaz.
            Yorumlarda markaların ticari itibarını zedeleyici, karalayıcı ve herhangi bir şekilde ticari zarara yol açabilecek yorumlar onaylanmayacak ve silinecektir. Aynı şekilde bir markaya yönelik promosyon veya reklam amaçlı yorumlar da onaylanmayacak ve silinecek yorumlar kategorisindedir. Başka hiçbir siteden alınan linkler Haberturk.com yorum sayfalarında paylaşılamaz.
            Haberturk.com yorum sayfalarında paylaşılan tüm yorumların yasal sorumluluğu yorumu yapan okura aittir ve Haberturk.com bunlardan sorumlu tutulamaz.
            Bizlerle ve diğer okurlarımızla yorum kurallarına uygun yorumlarınızı, görüşlerinizi yasalar, saygı, nezaket, birlikte yaşama kuralları ve insan haklarına uygun şekilde paylaştığınız için teşekkür ederiz.
            Şifrenizi sıfırlamak için oturum açarken kullandığınız e-posta adresinizi giriniz""")
            return a
        if a == "":
            for j in soup.select("p"):
                a = a + j.getText()
            return a


# sozcu
def sozcuSonDakika():
    r = requests.get("https://www.sozcu.com.tr/son-dakika/")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "timeline-card"})

    for new in news:
        link = new.a.get("href")
        head = new.find("img", attrs={"loading": "lazy"})
        image = head.get("src").replace("?w=220&h=165&mode=crop", "?w=800&h=300&mode=crop")
        contenttext = makale_cek(link)
        imgtitle = new.find("img", attrs={"loading": "lazy"})
        title = imgtitle.get("alt")

        req = requests.get(link)
        soup2 = BeautifulSoup(req.content, "lxml")
        datetime = soup2.find("time")
        datetime = datetime.text
        try:
            datetime = date_converter(datetime, "sözcü")
        except:
            break

        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "sözcü", link, "son dakika")

        else:
            break


def sozcuEkonomi():
    r = requests.get("https://www.sozcu.com.tr/kategori/ekonomi/")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "news-item"})

    for new in news:
        link = new.a.get("href")
        head = new.find("img", attrs={"loading": "lazy"})
        image = head.get("src").replace("?w=220&h=165&mode=crop", "?w=800&h=300&mode=crop").replace(
            "?w=243&h=136&mode=crop", "?w=800&h=300&mode=crop")
        contenttext = makale_cek(link)
        imgtitle = new.find("img", attrs={"loading": "lazy"})
        title = imgtitle.get("alt")
        req = requests.get(link)
        soup2 = BeautifulSoup(req.content, "lxml")
        datetime = soup2.find("time")
        datetime = datetime.text
        try:
            datetime = date_converter(datetime, "sözcü")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "sözcü", link, "ekonomi")

        else:
            break


def sozcuDunya():
    r = requests.get("https://www.sozcu.com.tr/kategori/dunya/")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "news-item"})

    for new in news:
        link = new.a.get("href")
        head = new.find("img", attrs={"loading": "lazy"})
        image = head.get("src").replace("?w=220&h=165&mode=crop", "?w=800&h=300&mode=crop").replace(
            "?w=243&h=136&mode=crop", "?w=800&h=300&mode=crop")
        contenttext = makale_cek(link)
        imgtitle = new.find("img", attrs={"loading": "lazy"})
        title = imgtitle.get("alt")
        req = requests.get(link)
        soup2 = BeautifulSoup(req.content, "lxml")
        datetime = soup2.find("time")
        datetime = datetime.text
        try:
            datetime = date_converter(datetime, "sözcü")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "sözcü", link, "dünya")

        else:
            break


def sozcuTekno():
    r = requests.get("https://www.sozcu.com.tr/kategori/teknoloji/")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "news-item"})

    for new in news:
        link = new.a.get("href")
        head = new.find("img", attrs={"loading": "lazy"})
        image = head.get("src").replace("?w=220&h=165&mode=crop", "?w=800&h=300&mode=crop").replace(
            "?w=243&h=136&mode=crop", "?w=800&h=300&mode=crop")
        contenttext = makale_cek(link)
        imgtitle = new.find("img", attrs={"loading": "lazy"})
        title = imgtitle.get("alt")
        req = requests.get(link)
        soup2 = BeautifulSoup(req.content, "lxml")
        datetime = soup2.find("time")
        datetime = datetime.text
        try:
            datetime = date_converter(datetime, "sözcü")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "sözcü", link, "teknoloji")

        else:
            break


# karar haber

def kararSonDakika():
    r = requests.get("https://www.karar.com/son-dakika")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("article", attrs={"class": "col-4"})

    for new in news:
        link = new.a.get("href")
        linkBasi = "https://www.karar.com"
        link = linkBasi + link

        head = new.find("img", attrs={"loading": "lazy"})
        title = head.get("alt")

        newPage = requests.get(link)
        soup = BeautifulSoup(newPage.content, "lxml")

        resim = soup.find("div", attrs={"class": "imgc"})
        if resim == None:
            image == "https://cdn.karar.com/news/1560680.jpg"
        else:
            image = resim.img.get("data-src")

        datetime = soup.find("time").text

        contenttext = makale_cek(link)

        try:
            datetime = date_converter(datetime, "karar")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "karar", link, "son dakika")

        else:
            break


def kararDunya():
    r = requests.get("https://www.karar.com/dunya-haberleri")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "col-4"})

    for new in news:

        link = new.a.get("href")
        linkBasi = "https://www.karar.com"
        link = linkBasi + link

        head = new.find("img", attrs={"loading": "lazy"})
        title = head.get("alt")
        newPage = requests.get(link)
        soup = BeautifulSoup(newPage.content, "lxml")

        resim = soup.find("div", attrs={"class": "imgc"})
        if resim == None:
            image == "https://cdn.karar.com/news/1560680.jpg"
        else:
            image = resim.img.get("data-src")

        datetime = soup.find("time").text

        contenttext = makale_cek(link)

        try:
            datetime = date_converter(datetime, "karar")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "karar", link, "dünya")

        else:
            break


def kararEkonomi():
    r = requests.get("https://www.karar.com/ekonomi-haberleri")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "col-4"})

    for new in news:

        link = new.a.get("href")
        linkBasi = "https://www.karar.com"
        link = linkBasi + link

        head = new.find("img", attrs={"loading": "lazy"})
        title = head.get("alt")
        newPage = requests.get(link)
        soup = BeautifulSoup(newPage.content, "lxml")

        resim = soup.find("div", attrs={"class": "imgc"})
        if resim == None:
            image == "https://cdn.karar.com/news/1560680.jpg"
        else:
            image = resim.img.get("data-src")

        datetime = soup.find("time").text

        contenttext = makale_cek(link)

        try:
            datetime = date_converter(datetime, "karar")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "karar", link, "ekonomi")

        else:
            break


def kararHayat():
    r = requests.get("https://www.karar.com/hayat-haberleri")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "col-4"})

    for new in news:

        link = new.a.get("href")
        linkBasi = "https://www.karar.com"
        link = linkBasi + link

        head = new.find("img", attrs={"loading": "lazy"})
        title = head.get("alt")
        newPage = requests.get(link)
        soup = BeautifulSoup(newPage.content, "lxml")

        resim = soup.find("div", attrs={"class": "imgc"})
        if resim == None:
            image == "https://cdn.karar.com/news/1560680.jpg"
        else:
            image = resim.img.get("data-src")

        datetime = soup.find("time").text

        contenttext = makale_cek(link)

        try:
            datetime = date_converter(datetime, "karar")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "karar", link, "hayat")

        else:
            break


# trt

def trtSonDakika():
    r = requests.get("https://www.trthaber.com/haber/gundem/")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "standard-left-thumb-card"})
    for new in news:
        link = new.a.get("href")
        title = new.a.get("title")
        try:

            newPage = requests.get(link)
            soup = BeautifulSoup(newPage.content, "lxml")
            datetime = soup.find("time").text
            resim = soup.find("div", attrs={"class": "news-image"})
            image = resim.img.get("data-src")
        except:
            image = "https://trthaberstatic.cdn.wp.trt.com.tr/resimler/2046000/19-mayis-anitkabir-aa-2047437.jpg"

        contenttext = str(makale_cek(link))
        contenttext = " ".join(contenttext.split())

        try:
            datetime = date_converter(datetime, "trt")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "trt", link, "son dakika")

        else:
            break


def trtDunya():
    r = requests.get("https://www.trthaber.com/haber/dunya/")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "standard-left-thumb-card"})
    for new in news:
        link = new.a.get("href")
        title = new.a.get("title")
        try:

            newPage = requests.get(link)
            soup = BeautifulSoup(newPage.content, "lxml")
            datetime = soup.find("time").text
            resim = soup.find("div", attrs={"class": "news-image"})
            image = resim.img.get("data-src")
        except:
            image = "https://trthaberstatic.cdn.wp.trt.com.tr/resimler/2046000/19-mayis-anitkabir-aa-2047437.jpg"

        contenttext = makale_cek(link)
        contenttext = " ".join(contenttext.split())
        try:
            datetime = date_converter(datetime, "trt")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "trt", link, "dünya")

        else:
            break


def trtEkonomi():
    r = requests.get("https://www.trthaber.com/haber/ekonomi/")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "standard-left-thumb-card"})
    for new in news:
        link = new.a.get("href")
        title = new.a.get("title")
        try:

            newPage = requests.get(link)
            soup = BeautifulSoup(newPage.content, "lxml")
            datetime = soup.find("time").text
            resim = soup.find("div", attrs={"class": "news-image"})
            image = resim.img.get("data-src")
        except:
            image = "https://trthaberstatic.cdn.wp.trt.com.tr/resimler/2046000/19-mayis-anitkabir-aa-2047437.jpg"

        contenttext = makale_cek(link)
        contenttext = " ".join(contenttext.split())
        try:
            datetime = date_converter(datetime, "trt")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "trt", link, "ekonomi")

        else:
            break


def trtTeknoloji():
    r = requests.get("https://www.trthaber.com/haber/bilim-teknoloji/")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "standard-left-thumb-card"})
    for new in news:
        link = new.a.get("href")
        title = new.a.get("title")
        try:

            newPage = requests.get(link)
            soup = BeautifulSoup(newPage.content, "lxml")
            datetime = soup.find("time").text
            resim = soup.find("div", attrs={"class": "news-image"})
            image = resim.img.get("data-src")
        except:
            image = "https://trthaberstatic.cdn.wp.trt.com.tr/resimler/2046000/19-mayis-anitkabir-aa-2047437.jpg"

        contenttext = makale_cek(link)
        contenttext = " ".join(contenttext.split())
        try:
            datetime = date_converter(datetime, "trt")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "trt", link, "teknoloji")

        else:
            break


# Son dakika haber sitesi

def sonDakika():
    r = requests.get("https://www.sondakika.com/guncel/")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("li", attrs={"class": "nws"})
    for new in news:
        link = new.a.get("href")
        linkBasi = "https://www.sondakika.com/"
        link = linkBasi + link
        title = new.a.get("title")
        try:
            newPage = requests.get(link)
            soup = BeautifulSoup(newPage.content, "lxml")
            datetime = soup.find("div", attrs={"class": "hbptDate"}).text
            resim = soup.find("div", attrs={"class": "haberResim"})
            image = resim.img.get("src")
        except:
            image = "https://trthaberstatic.cdn.wp.trt.com.tr/resimler/2046000/19-mayis-anitkabir-aa-2047437.jpg"
        contenttext = makale_cek(link)

        try:
            datetime = date_converter(datetime, "son dakika")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "son dakika", link, "son dakika")

        else:
            break


def sonEkonomi():
    r = requests.get("https://www.sondakika.com/ekonomi/")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("li", attrs={"class": "nws"})
    for new in news:
        link = new.a.get("href")
        linkBasi = "https://www.sondakika.com/"
        link = linkBasi + link
        title = new.a.get("title")
        try:
            newPage = requests.get(link)
            soup = BeautifulSoup(newPage.content, "lxml")
            datetime = soup.find("div", attrs={"class": "hbptDate"}).text
            resim = soup.find("div", attrs={"class": "haberResim"})
            image = resim.img.get("src")
        except:
            image = "https://trthaberstatic.cdn.wp.trt.com.tr/resimler/2046000/19-mayis-anitkabir-aa-2047437.jpg"
        contenttext = makale_cek(link)
        try:
            datetime = date_converter(datetime, "son dakika")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "son dakika", link, "ekonomi")

        else:
            break


def sonMagazin():
    r = requests.get("https://www.sondakika.com/magazin/")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("li", attrs={"class": "nws"})
    for new in news:
        link = new.a.get("href")
        linkBasi = "https://www.sondakika.com/"
        link = linkBasi + link
        title = new.a.get("title")
        try:
            newPage = requests.get(link)
            soup = BeautifulSoup(newPage.content, "lxml")
            datetime = soup.find("div", attrs={"class": "hbptDate"}).text
            resim = soup.find("div", attrs={"class": "haberResim"})
            image = resim.img.get("src")
        except:
            image = "https://trthaberstatic.cdn.wp.trt.com.tr/resimler/2046000/19-mayis-anitkabir-aa-2047437.jpg"
        contenttext = makale_cek(link)
        datetime = date_converter(datetime, "son dakika")
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "son dakika", link, "magazin")

        else:
            break


def sonSpor():
    r = requests.get("https://www.sondakika.com/spor/")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("li", attrs={"class": "nws"})
    for new in news:
        link = new.a.get("href")
        linkBasi = "https://www.sondakika.com/"
        link = linkBasi + link
        title = new.a.get("title")
        try:
            newPage = requests.get(link)
            soup = BeautifulSoup(newPage.content, "lxml")
            datetime = soup.find("div", attrs={"class": "hbptDate"}).text
            resim = soup.find("div", attrs={"class": "haberResim"})
            image = resim.img.get("src")
        except:
            image = "https://trthaberstatic.cdn.wp.trt.com.tr/resimler/2046000/19-mayis-anitkabir-aa-2047437.jpg"
        contenttext = makale_cek(link)
        try:
            datetime = date_converter(datetime, "son dakika")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "son dakika", link, "spor")

        else:
            break


# Gerçek gündem

def ggSonDakika():
    r = requests.get("https://www.gercekgundem.com/guncel")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "col-sm-6"})
    for new in news:
        link = new.a.get("href")
        title = new.a.get("title")
        image = new.img.get("src")

        try:
            newPage = requests.get(link)
            soup = BeautifulSoup(newPage.content, "lxml")
            datetime = soup.find("time").text
        except:
            image = "https://trthaberstatic.cdn.wp.trt.com.tr/resimler/2046000/19-mayis-anitkabir-aa-2047437.jpg"

        contenttext = makale_cek(link)
        try:
            datetime = date_converter(datetime, "gerçek gündem")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "gerçek gündem", link, "son dakika")

        else:
            break


def ggDunya():
    r = requests.get("https://www.gercekgundem.com/dunya")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "col-sm-6"})
    for new in news:
        link = new.a.get("href")
        title = new.a.get("title")
        image = new.img.get("src")

        try:
            newPage = requests.get(link)
            soup = BeautifulSoup(newPage.content, "lxml")
            datetime = soup.find("time").text
        except:
            image = "https://trthaberstatic.cdn.wp.trt.com.tr/resimler/2046000/19-mayis-anitkabir-aa-2047437.jpg"

        contenttext = makale_cek(link)
        try:
            datetime = date_converter(datetime, "gerçek gündem")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "gerçek gündem", link, "dünya")

        else:
            break


def ggEkonomi():
    r = requests.get("https://www.gercekgundem.com/ekonomi")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "col-sm-6"})
    for new in news:
        link = new.a.get("href")
        title = new.a.get("title")
        image = new.img.get("src")

        try:
            newPage = requests.get(link)
            soup = BeautifulSoup(newPage.content, "lxml")
            datetime = soup.find("time").text
        except:
            image = "https://trthaberstatic.cdn.wp.trt.com.tr/resimler/2046000/19-mayis-anitkabir-aa-2047437.jpg"

        contenttext = makale_cek(link)
        try:
            datetime = date_converter(datetime, "gerçek gündem")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "gerçek gündem", link, "ekonomi")

        else:
            break


def ggHayat():
    r = requests.get("https://www.gercekgundem.com/yasam")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "col-sm-6"})
    for new in news:
        link = new.a.get("href")
        title = new.a.get("title")
        image = new.img.get("src")

        try:
            newPage = requests.get(link)
            soup = BeautifulSoup(newPage.content, "lxml")
            datetime = soup.find("time").text
        except:
            image = "https://trthaberstatic.cdn.wp.trt.com.tr/resimler/2046000/19-mayis-anitkabir-aa-2047437.jpg"

        contenttext = makale_cek(link)
        try:
            datetime = date_converter(datetime, "gerçek gündem")
        except:
            break
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            saveToDatabase(title, image, contenttext, datetime, "gerçek gündem", link, "hayat")

        else:
            break
@app.route("/")
def main():
    return render_template("index.html")
@app.route("/<string:newstype>/<int:sayi>",methods = ["GET"])
def haber(newstype,sayi):
    if newstype == "son-dakika":
        a = cursor.execute(f"select * from News where type = 'sondakika' order by date desc limit {sayi} ")
        return a.fetchall()
    if newstype == "ekonomi":
        a = cursor.execute(f"select * from News where type = 'ekonomi' order by date desc limit {sayi} ")
        return a.fetchall()
    if newstype == "spor":
        a = cursor.execute(f"select * from News where type = 'spor' order by date desc limit {sayi} ")
        return a.fetchall()
    if newstype == "dunya":
        a = cursor.execute(f"select * from News where type = 'dunya' order by date desc limit {sayi} ")
        return a.fetchall()
    if newstype == "otomotiv":
        a = cursor.execute(f"select * from News where type = 'otomotiv' order by date desc limit {sayi} ")
        return a.fetchall()

@app.route("/<string:newstype>/today",methods = ["GET"])
def tumHaberler(newstype):
    today = str(date.today().strftime("%Y %m %d")).replace(" ","-")


    if newstype == "son-dakika":
        a = cursor.execute(f"select news_id,title,image,text,luhn,lexrank,lsa,textrank,giso,ortayol,all_in_one,date,site_name,url_link,type from News,Summarizers where News.news_id = Summarizers.new_id and News.type = 'son dakika' and News.date like '{today}%' order by date desc  ")
        return a.fetchall()
    if newstype == "ekonomi":
        a = cursor.execute(f"select news_id,title,image,text,luhn,lexrank,lsa,textrank,giso,ortayol,all_in_one,date,site_name,url_link,type from News,Summarizers where News.news_id = Summarizers.new_id and News.type = 'ekonomi' and News.date like '{today}%' order by date desc ")
        return a.fetchall()
    if newstype == "spor":
        a = cursor.execute(f"select news_id,title,image,text,luhn,lexrank,lsa,textrank,giso,ortayol,all_in_one,date,site_name,url_link,type from News,Summarizers where News.news_id = Summarizers.new_id and News.type = 'spor' and News.date like '{today}%' order by date desc  ")
        return a.fetchall()
    if newstype == "dunya":
        a = cursor.execute(f"select news_id,title,image,text,luhn,lexrank,lsa,textrank,giso,ortayol,all_in_one,date,site_name,url_link,type from News,Summarizers where News.news_id = Summarizers.new_id and News.type = 'dünya' and News.date like '{today}%' order by date desc ")
        return a.fetchall()
    if newstype == "magazin":
        a = cursor.execute(f"select news_id,title,image,text,luhn,lexrank,lsa,textrank,giso,ortayol,all_in_one,date,site_name,url_link,type from News,Summarizers where News.news_id = Summarizers.new_id and News.type = 'magazin' and News.date like '{today}%' order by date desc")
        return a.fetchall()
    if newstype == "hayat":
        a = cursor.execute(f"select news_id,title,image,text,luhn,lexrank,lsa,textrank,giso,ortayol,all_in_one,date,site_name,url_link,type from News,Summarizers where News.news_id = Summarizers.new_id and News.type = 'hayat' and News.date like '{today}%' order by date desc")
        return a.fetchall()
    if newstype == "teknoloji":
        a = cursor.execute(f"select news_id,title,image,text,luhn,lexrank,lsa,textrank,giso,ortayol,all_in_one,date,site_name,url_link,type from News,Summarizers where News.news_id = Summarizers.new_id and News.type = 'teknoloji' and News.date like '{today}%' order by date desc")
        return a.fetchall()

@app.route("/<string:newstype>/today/<string:attr>",methods = ["GET"])
def BugunkuHaberlerAlg(newstype,attr):
    today = str(date.today().strftime("%Y %m %d")).replace(" ","-")
    if newstype == "son dakika":
        a = cursor.execute(
            f"select news_id,title,image,{attr},date,site_name,url_link from News,Summarizers where News.news_id = Summarizers.new_id and type = 'son dakika' and date like '{today}%' order by date desc ")
        return a.fetchall()
    if newstype == "ekonomi":
        a = cursor.execute(
            f"select news_id,title,image,{attr},date,site_name,url_link from News,Summarizers where News.news_id = Summarizers.new_id and type = 'ekonomi' and date like '{today}%' order by date desc  ")
        return a.fetchall()
    if newstype == "spor":
        a = cursor.execute(
            f"select news_id,title,image,{attr},date,site_name,url_link from News,Summarizers where News.news_id = Summarizers.new_id and type = 'spor' and date like '{today}%' order by date desc ")
        return a.fetchall()
    if newstype == "dunya":
        a = cursor.execute(
            f"select news_id,title,image,{attr},date,site_name,url_link from News,Summarizers where News.news_id = Summarizers.new_id and type = 'dünya' and date like '{today}%' order by date desc ")
        return a.fetchall()
    if newstype == "hayat":
        a = cursor.execute(
            f"select news_id,title,image,{attr},date,site_name,url_link from News,Summarizers where News.news_id = Summarizers.new_id and type = 'hayat' and date like '{today}%' order by date desc  ")
        return a.fetchall()
    if newstype == "magazin":
        a = cursor.execute(
            f"select news_id,title,image,{attr},date,site_name,url_link from News,Summarizers where News.news_id = Summarizers.new_id and type = 'magazin' and date like '{today}%' order by date desc  ")
        return a.fetchall()
    if newstype == "teknoloji":
        a = cursor.execute(
            f"select news_id,title,image,{attr},date,site_name,url_link from News,Summarizers where News.news_id = Summarizers.new_id and type = 'teknoloji' and date like '{today}%' order by date desc  ")
        return a.fetchall()
@app.route("/habergirisi/sozcu")
def sozcuHaberGetir():
    sozcuSonDakika()
    sozcuDunya()
    sozcuTekno()
    sozcuEkonomi()
    return "tüm haberler kaydedildi."
@app.route("/habergirisi/karar")
def kararHaberGetir():
    kararSonDakika()
    kararDunya()
    kararHayat()
    kararEkonomi()
    return "tüm haberler kaydedildi."
@app.route("/habergirisi/gg")
def ggHaberGetir():
    ggSonDakika()
    ggDunya()
    ggHayat()
    ggEkonomi()
    return "tüm haberler kaydedildi."
@app.route("/habergirisi/trt")
def trtHaberGetir():
    trtSonDakika()
    trtDunya()
    trtTeknoloji()
    trtEkonomi()
    return "tüm haberler kaydedildi."
@app.route("/habergirisi/son-dakika")
def sonHaberGetir():
    sonDakika()
    sonSpor()
    sonEkonomi()
    sonMagazin()
    return "tüm haberler kaydedildi."

@app.route("/<string:newstype>/<int:sayi>/<string:attr>",methods = ["GET"])
def haber_bilgileri(newstype,sayi,attr):
    if newstype == "son-dakika":
        a = cursor.execute(f"select news_id,title,image,{attr},date,site_name,url_link from News,Summarizers where News.news_id = Summarizers.new_id and type = 'sondakika' order by date desc limit {sayi} ")
        return a.fetchall()
    if newstype == "ekonomi":
        a = cursor.execute(
            f"select news_id,title,image,{attr},date,site_name,url_link from News,Summarizers where News.news_id = Summarizers.new_id and type = 'ekonomi' order by date desc limit {sayi} ")
        return a.fetchall()
    if newstype == "spor":
        a = cursor.execute(
            f"select news_id,title,image,{attr},date,site_name,url_link from News,Summarizers where News.news_id = Summarizers.new_id and type = 'spor' order by date desc limit {sayi} ")
        return a.fetchall()
    if newstype == "dunya":
        a = cursor.execute(
            f"select news_id,title,image,{attr},date,site_name,url_link from News,Summarizers where News.news_id = Summarizers.new_id and type = 'dunya' order by date desc limit {sayi} ")
        return a.fetchall()
    if newstype == "otomotiv":
        a = cursor.execute(
            f"select news_id,title,image,{attr},date,site_name,url_link from News,Summarizers where News.news_id = Summarizers.new_id and type = 'otomotiv' order by date desc limit {sayi} ")
        return a.fetchall()
@app.route("/register",methods = ['POST'])
def kullanıcıKaydet():
    try:
        tempName = request.json["name"]
        tempSurname = request.json["surname"]
    except:
        tempName= None
        tempSurname = None
    tempMail = request.json["mail"]
    tempUsername = request.json["username"]
    tempPassword = request.json["password"]
    tempPhoneNumber = request.json["phone"]
    if cursor.execute(f"select * from Users where mail = '{tempMail}'").fetchone() != None or cursor.execute(f"select * from Users where username = '{tempUsername}'").fetchone() != None or cursor.execute(f"select * from Users where phone_number = '{tempPhoneNumber}'").fetchone() != None:
        return("User already exists")

    else:
        tempPassword = str(tempPassword).encode('utf-8')
        tempPassword = bcrypt.hashpw(tempPassword, bcrypt.gensalt())

        cursor.execute("insert into Users(name,surname,mail,username,password,phone_number) Values(?,?,?,?,?,?)",
                       (tempName, tempSurname, tempMail, tempUsername, tempPassword, tempPhoneNumber))
        con.commit()
        return ("Success")

@app.route("/login",methods = ["POST"])
def loginAuth():
    data = request.json["data"]
    pwd = str(request.json["password"]).encode("utf-8")
    valid = False

    if "@" in data:
        if cursor.execute(f"select password from Users where mail = '{data}' ").fetchone() != None:
            hashed_pwd = cursor.execute(f"select password from Users where mail = '{data}' ").fetchone()[0]
            if bcrypt.checkpw(pwd,hashed_pwd):
                valid = True
    else:

        if cursor.execute(f"select password from Users where phone_number = '{data}' ").fetchone() != None:
            hashed_pwd = cursor.execute(f"select password from Users where phone_number = '{data}'").fetchone()[0]
            if bcrypt.checkpw(pwd,hashed_pwd):
                valid = True
        if cursor.execute(f"select password from Users where username = '{data}' ").fetchone() != None:
            hashed_pwd = cursor.execute(f"select password from Users where username = '{data}'").fetchone()[0]
            if bcrypt.checkpw(pwd,hashed_pwd):
                valid = True
    return str(valid)

@app.route("/post-alarm",methods = ["POST"])
def postAlarm():
    user_id = str(request.json["user_id"])
    date = str(request.json["date"])
    type = str(request.json["type"])
    if len(cursor.execute(f"select * from Alarms where user_id = '{user_id}' and date = '{date}' and type = '{type}'").fetchall()) > 0:
        return "Hata: Kullanıcı aynı alarmı kaydetmeye çalışıyor."

    cursor.execute(f"insert into Alarms(user_id,date,type) values(?,?,?)",(user_id,date,type))
    con.commit()
    return "Alarm başarıyla kaydedildi..."
@app.route("/get-alarms/<int:user_id>",methods = ["GET"])
def getAlarms(user_id):
    now = datetime.now()

    # Saati 3 saat ileri almak için timedelta kullanma
    now = now + timedelta(hours=3)
    now = now.strftime("%Y-%m-%d %H:%M")

    return cursor.execute(f"select * from Alarms where user_id = '{user_id}' and date >= '{now}' order by date").fetchall()

@app.route("/check-alarms/<int:user_id>",methods = ["GET"])
def checkAlarms(user_id):
    now = datetime.now()

    # Saati 3 saat ileri almak için timedelta kullanma
    now = now + timedelta(hours=3)
    now = now.strftime("%Y-%m-%d %H:%M")

    last_user_alarm_date = cursor.execute(f"select date from Alarms where user_id = '{user_id}'and date < '{now}' order by date desc").fetchone()
    if last_user_alarm_date == None:
        return "false"
    type_list = []
    user_alarm_types = cursor.execute(f"SELECT type FROM Alarms WHERE user_id = ? and date = ?",
                                      (user_id, last_user_alarm_date[0])).fetchall()

    for item_type in user_alarm_types:
        type_list.append(item_type[0])

    if len(type_list) > 0:
        placeholders = ', '.join(['?'] * len(type_list))
        query = f"select news_id,title,image,text,luhn,lexrank,lsa,textrank,giso,ortayol,all_in_one,date,site_name,url_link,type from News,Summarizers where News.news_id = Summarizers.new_id and News.type IN ({placeholders}) and date <= '{last_user_alarm_date[0]}'order by date desc limit 40"
        news_results = cursor.execute(query, type_list).fetchall()
        return jsonify(news_results)

    return "false"

@app.route("/delete-alarm",methods = ["DELETE"])
def deleteAlarms():
    user_id = request.json["user_id"]
    date = str(request.json["date"])
    type = str(request.json["type"])
    if len(cursor.execute(f"select * from Alarms where user_id = '{user_id}' and date = '{date}' and type = '{type}'").fetchall()) > 0:
        cursor.execute(f"delete from Alarms where user_id = ? and date = ? and type = ?" , (user_id, date,type))
        con.commit()
        return "başarıyla silindi"
    return "hata,böyle bir alarm yok"

@app.route("/user-id/<string:data>",methods = ["GET"])
def kullanıcı(data):
    return jsonify(cursor.execute(f"select user_id from Users where username = '{data}' or phone_number = '{data}' or mail = '{data}'").fetchall())





if __name__ == "__main__":
    app.run();