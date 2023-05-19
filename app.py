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

def sozcu_tarih(tarih):
    b = tarih.split(" ")
    b[3] = month_dict[b[3]]
    c = b[2] + " " + b[3] + " " + b[4] + " " + b[1] + " " + b[0]
    return c

class Haber():
    def __init__(self,baslik,resim,metin,tarih):
        self.baslik = baslik
        self.resim = resim
        self.metin = metin
        self.tarih = tarih

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

def scrapingSonDakika():
    r = requests.get("https://www.sozcu.com.tr/son-dakika/")
    soup = BeautifulSoup(r.content,"lxml")
    news = soup.find_all("div",attrs={"class":"timeline-card"})

    for new in news:
        link = new.a.get("href")
        head = new.find("img", attrs={"loading": "lazy"})
        image = head.get("src").replace("?w=220&h=165&mode=crop", "?w=800&h=300&mode=crop")
        contentText = makale_cek(link)
        imgtitle = new.find("img", attrs={"loading": "lazy"})
        title = imgtitle.get("alt")

        req = requests.get(link)
        soup2 = BeautifulSoup(req.content,"lxml")
        datetime = soup2.find("time")
        dateformat = datetime.text


        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            cursor.execute("insert into News (title,image,text,date,site_name,url_link,type) values (?,?,?,?,?,?,?) ",(title,image,contentText,sozcu_tarih(datetime.text),"sozcu",link,"sondakika"))
            con.commit()
            id = cursor.execute(f"select news_id from News where url_link = '{link}'").fetchone()
            cursor.execute(f"insert into Summarizers(new_id,luhn,lexrank,lsa,textrank,giso,ortayol,all_in_one) values (?,?,?,?,?,?,?,?)",(id[0],luhn(contentText),lex_rank(contentText),lsa_summary(contentText),textrank(contentText),giso(contentText),ortayol(contentText),all_in_one(contentText)))
            con.commit()
        else:
            break


def scrapingEkonomi():
    r = requests.get("https://www.sozcu.com.tr/kategori/ekonomi/")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "news-item"})

    for new in news:
        link = new.a.get("href")
        head = new.find("img", attrs={"loading": "lazy"})
        image = head.get("src").replace("?w=220&h=165&mode=crop", "?w=800&h=300&mode=crop").replace(
            "?w=243&h=136&mode=crop", "?w=800&h=300&mode=crop")
        contentText = makale_cek(link)
        imgtitle = new.find("img", attrs={"loading": "lazy"})
        title = imgtitle.get("alt")
        req = requests.get(link)
        soup2 = BeautifulSoup(req.content, "lxml")
        datetime = soup2.find("time")
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            cursor.execute("insert into News (title,image,text,date,site_name,url_link,type) values (?,?,?,?,?,?,?) ",
                           (title, image, contentText, sozcu_tarih(datetime.text), "sozcu", link, "ekonomi"))
            con.commit()
            id = cursor.execute(f"select news_id from News where url_link = '{link}'").fetchone()
            cursor.execute(
                f"insert into Summarizers(new_id,luhn,lexrank,lsa,textrank,giso,ortayol,all_in_one) values (?,?,?,?,?,?,?,?)",
                (id[0], luhn(contentText), lex_rank(contentText), lsa_summary(contentText), textrank(contentText),
                 giso(contentText), ortayol(contentText), all_in_one(contentText)))
            con.commit()
        else:
            break

def scrapingSpor():
    r = requests.get("https://www.sozcu.com.tr/kategori/spor")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "news-item"})

    for new in news:
        link = new.a.get("href")
        head = new.find("img", attrs={"loading": "lazy"})
        image = head.get("src").replace("?w=220&h=165&mode=crop", "?w=800&h=300&mode=crop").replace(
            "?w=243&h=136&mode=crop", "?w=800&h=300&mode=crop")
        contentText = makale_cek(link)
        if contentText == "Güncel HaberlerDöviz K":
            contentText = "Site kaynaklı içerik hatası..."
        imgtitle = new.find("img", attrs={"loading": "lazy"})
        title = imgtitle.get("alt")
        req = requests.get(link)
        soup2 = BeautifulSoup(req.content, "lxml")
        datetime = soup2.find("time")
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            cursor.execute("insert into News (title,image,text,date,site_name,url_link,type) values (?,?,?,?,?,?,?) ",
                           (title, image, contentText, sozcu_tarih(datetime.text), "sozcu", link, "spor"))
            con.commit()
            id = cursor.execute(f"select news_id from News where url_link = '{link}'").fetchone()
            cursor.execute(
                f"insert into Summarizers(new_id,luhn,lexrank,lsa,textrank,giso,ortayol,all_in_one) values (?,?,?,?,?,?,?,?)",
                (id[0], luhn(contentText), lex_rank(contentText), lsa_summary(contentText), textrank(contentText),
                 giso(contentText), ortayol(contentText), all_in_one(contentText)))
            con.commit()
        else:
            break

def scrapingDunya():
    r = requests.get("https://www.sozcu.com.tr/kategori/dunya/")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "news-item"})

    for new in news:
        link = new.a.get("href")
        head = new.find("img", attrs={"loading": "lazy"})
        image = head.get("src").replace("?w=220&h=165&mode=crop", "?w=800&h=300&mode=crop").replace(
            "?w=243&h=136&mode=crop", "?w=800&h=300&mode=crop")
        contentText = makale_cek(link)
        imgtitle = new.find("img", attrs={"loading": "lazy"})
        title = imgtitle.get("alt")
        req = requests.get(link)
        soup2 = BeautifulSoup(req.content, "lxml")
        datetime = soup2.find("time")
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            cursor.execute("insert into News (title,image,text,date,site_name,url_link,type) values (?,?,?,?,?,?,?) ",
                           (title, image, contentText, sozcu_tarih(datetime.text), "sozcu", link, "dunya"))
            con.commit()
            id = cursor.execute(f"select news_id from News where url_link = '{link}'").fetchone()
            cursor.execute(
                f"insert into Summarizers(new_id,luhn,lexrank,lsa,textrank,giso,ortayol,all_in_one) values (?,?,?,?,?,?,?,?)",
                (id[0], luhn(contentText), lex_rank(contentText), lsa_summary(contentText), textrank(contentText),
                 giso(contentText), ortayol(contentText), all_in_one(contentText)))
            con.commit()
        else:
            break

def scrapingOtomotiv():
    r = requests.get("https://www.sozcu.com.tr/kategori/otomotiv/")
    soup = BeautifulSoup(r.content, "lxml")
    news = soup.find_all("div", attrs={"class": "news-item"})

    for new in news:
        link = new.a.get("href")
        head = new.find("img", attrs={"loading": "lazy"})
        image = head.get("src").replace("?w=220&h=165&mode=crop", "?w=800&h=300&mode=crop").replace(
            "?w=243&h=136&mode=crop", "?w=800&h=300&mode=crop")
        contentText = makale_cek(link)
        imgtitle = new.find("img", attrs={"loading": "lazy"})
        title = imgtitle.get("alt")
        req = requests.get(link)
        soup2 = BeautifulSoup(req.content, "lxml")
        datetime = soup2.find("time")
        link_list = cursor.execute(f"select * from News where url_link = '{link}'")
        if len(link_list.fetchall()) == 0:
            cursor.execute("insert into News (title,image,text,date,site_name,url_link,type) values (?,?,?,?,?,?,?) ",
                           (title, image, contentText,sozcu_tarih(datetime.text), "sozcu", link, "otomotiv"))
            con.commit()
            id = cursor.execute(f"select news_id from News where url_link = '{link}'").fetchone()
            cursor.execute(
                f"insert into Summarizers(new_id,luhn,lexrank,lsa,textrank,giso,ortayol,all_in_one) values (?,?,?,?,?,?,?,?)",
                (id[0], luhn(contentText), lex_rank(contentText), lsa_summary(contentText), textrank(contentText),
                 giso(contentText), ortayol(contentText), all_in_one(contentText)))
            con.commit()
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
    today = date.today().strftime("%d %m %Y")
    if newstype == "son-dakika":
        a = cursor.execute(f"select * from News where type = 'sondakika' and date like '{today}%' order by date desc  ")
        return a.fetchall()
    if newstype == "ekonomi":
        a = cursor.execute(f"select * from News where type = 'ekonomi' and date like '{today}%' order by date desc ")
        return a.fetchall()
    if newstype == "spor":
        a = cursor.execute(f"select * from News where type = 'spor' and date like '{today}%' order by date desc  ")
        return a.fetchall()
    if newstype == "dunya":
        a = cursor.execute(f"select * from News where type = 'dunya' and date like '{today}%' order by date desc ")
        return a.fetchall()
    if newstype == "otomotiv":
        a = cursor.execute(f"select * from News where type = 'otomotiv' and date like '{today}%' order by date desc")
        return a.fetchall()

@app.route("/<string:newstype>/today/<string:attr>",methods = ["GET"])
def BugunkuHaberlerAlg(newstype,attr):
    today = date.today().strftime("%d %m %Y")
    if newstype == "son-dakika":
        a = cursor.execute(
            f"select news_id,title,image,{attr},date,site_name,url_link from News,Summarizers where News.news_id = Summarizers.new_id and type = 'sondakika' and date like '{today}%' order by date desc ")
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
            f"select news_id,title,image,{attr},date,site_name,url_link from News,Summarizers where News.news_id = Summarizers.new_id and type = 'dunya' and date like '{today}%' order by date desc ")
        return a.fetchall()
    if newstype == "otomotiv":
        a = cursor.execute(
            f"select news_id,title,image,{attr},date,site_name,url_link from News,Summarizers where News.news_id = Summarizers.new_id and type = 'otomotiv' and date like '{today}%' order by date desc  ")
        return a.fetchall()
@app.route("/habergirisi")
def habergetir():
    haberGirişi()
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
        tempPassword = tempPassword.encode('utf-8')
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
        try:
            print(int(data))
            if cursor.execute(f"select password from Users where phone_number = '{data}' ").fetchone() != None:
                hashed_pwd = cursor.execute(f"select password from Users where phone_number = '{data}'").fetchone()[0]
                if bcrypt.checkpw(pwd,hashed_pwd):
                    valid = True
        except:
            if cursor.execute(f"select password from Users where username = '{data}' ").fetchone() != None:
                hashed_pwd = cursor.execute(f"select password from Users where username = '{data}'").fetchone()[0]
                if bcrypt.checkpw(pwd,hashed_pwd):
                    valid = True
    return str(valid)

def haberGirişi():
    scrapingSonDakika()
    scrapingEkonomi()
    scrapingDunya()
    scrapingOtomotiv()


if __name__ == "__main__":
    app.run();