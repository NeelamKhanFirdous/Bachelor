import fitz
import sys
import os
from pprint import pprint
from io import BytesIO
import pandas as pd
from spacy.matcher import Matcher
import spacy
import re


pollutants_no_number = ["NO₂", "NOx", "NO", "PM", "BC", "CO", "O", "SO", "NH", "NMVOCS", "VOCs", "VOC", "VOCS", "AOD", "AQI", "BCFF", "BCWB", "OM", "BBOA", "HOA", "OOA", "PMPM", "NO2", "PM2.5", "PM10", "NOX", "O3", "SO2", "NH3", "NO3", "SO4"]
pollutants_numbers = ["2", "2.5", "10", "X", "3", "4"]

negative = ["decrease", "reduce", "drop", "decline", "plummet", "reduction", "lower", "-", "low", "negative", "improve"]
positive = ["+", "increase", "positive", "rise"]
trend = negative + positive
number_regex = "[-,+,~]?[0-9]+,?[0-9]*[–,–]?[0-9]*,?[0-9]*"
highlighted_sentences = []


def extract_text(directory):
    """
    This function is for extracting the basics
    :param directory: the directory where we find the files that need extraction
    :return:
    """

    def find_value(span):

        pol = ""
        up = False
        down = True
        for tok in span:
            # print(tok.text + " --> " + tok.pos_ + " -> " + tok.dep_)
            if tok.text in pollutants_no_number:
                pol = tok.text
            # check if the trend is negative or positive
            elif tok.lemma_ in negative or tok.text[0] == "-":
                down = True
            elif tok.lemma_ in positive or tok.text[0] == "+":
                down = False
            # add the actual numerical value of the pollutant
            elif re.search(number_regex, tok.text) and tok.nbor().text == "%":
                # print("############################")
                # print(file)

                # check if the text contains more than just the number
                text = tok.text
                if text[0] in ["−", "+", "~"]:
                    text = text[1:]
                if "%" in text:
                    text = text.split("%")[0]
                if "e" in text:
                    text = text.split("e")[0]
                if "~" in text:
                    text = text.split("~")[0]
                if "-" in text[1:]:
                    v = text.split("-")
                    try:
                        text = str(round((float(v[0]) + float(v[1]))/2, 2))
                    except ValueError:
                        print(v)
                        print("contains not only numbers")
                        print(tok.sent)
                        break
                if "–" in text[1:]:
                    v = text.split("–")
                    try:
                        text = str(round((float(v[0]) + float(v[1]))/2, 2))
                    except ValueError:
                        print(v)
                        print("contains not only numbers")
                        print(tok.sent)
                        break
                try:
                    number = float(text)
                except ValueError:
                    print(tok.text + " is no number")
                    print(tok.sent)
                    break
                value = str(number)
                if down:
                    value = "-" + value

                # add the matched value to our current article data. If there is already a value stored for the pollutant, we will add it to the list
                if pol not in article_data:
                    article_data[pol] = [value]
                elif value not in article_data[pol]:
                    article_data[pol].append(value)

        # call the highlight function to highlight the pattern in the text
        highlight_match(span.sent.text)

    def highlight_match(text):
        """
        This function creates a new PDF file with the corresponding text passage highlighted
        :param text: the text that will be highlighted
        :return:
        """
        # check if already highlighted
        if text in highlighted_sentences:
            return

        output_buffer = BytesIO()

        area = page.search_for(text)
        if not len(area) == 0:
            highlight = page.add_highlight_annot(area)
            highlight.update()
            print("Highlighted " + text)
            highlighted_sentences.append(text)
        pdf.save(output_buffer)
        with open("./highlighted/" + file + "_highlighted.pdf", mode="wb") as f:
            f.write(output_buffer.getbuffer())

    def basic_pattern_match(matcher, doc, i, matches):
        """
        This function gets called once the firstMatcher found his pattern in the text.
        It then processes the match and extracts the information regarding the pollutants.
        :param matcher: the matcher which invoked this function
        :param doc: the document on which it searched
        :param i: the position of the current match
        :param matches: the total list of matches
        :return:
        """
        match_id, start, end = matches[i]

        # this is the extracted passage in the text
        span = doc[start:end]

        # these are the previous few words, to check if there are multiple pollutants in one sentence because if so, we have to ignore it
        span_previous = doc[start-3:start]
        if span_previous[2].text in ["and", ","]:
            if span_previous[1].text in pollutants_no_number or span_previous[1].text in pollutants_numbers:
                return
            if span_previous[1].text == "," and span_previous[0].text in pollutants_no_number or span_previous[0].text in pollutants_numbers:
                return

        find_value(span)

    def no_pollutant_match(matcher, doc, i, matches):
        """
        This function gets called once the no_poll_matcher found his pattern in the text.
        It then processes the match and extracts the information regarding the pollutants.
        :param matcher: the matcher which invoked this function
        :param doc: the document on which it searched
        :param i: the position of the current match
        :param matches: the total list of matches
        :return:
        """

        match_id, start, end = matches[i]

        # this is the extracted passage in the text
        span = doc[start:end]

        # get the previous sentence to find the pollutant
        prev_sent = ""
        first_token = span[0]
        index = first_token.i
        for k in reversed(range(index)):
            token = doc[k]
            if token.is_sent_end:
                prev_sent = token.sent
                break

        # check if there was a pollutant in the previous sentence
        pols = get_all_pollutants(prev_sent)
        if not pols:
            if type(prev_sent) == str:
                return
            # look at the previous sentence
            first_token = prev_sent[0]
            index = first_token.i
            for k in reversed(range(index)):
                token = doc[k]
                if token.is_sent_end:
                    prev_sent = token.sent
                    break
            pols = get_all_pollutants(prev_sent)
            if not pols:
                return
        pol = pols[-1]
        # and get the values for the pollutant in the current sentence
        values = get_values(span)
        # add the matched value to our current article data. If there is already a value stored for the pollutant, we will add it to the list
        if pol not in article_data:
            article_data[pol] = values
        else:
            for value in values:
                if value not in article_data[pol]:
                    article_data[pol].append(value)

        # call the highlight function to highlight the pattern in the text
        highlight_match(span.sent.text)

    def bracket_matcher(matcher, doc, i, matches):
        match_id, start, end = matches[i]

        # this is the extracted passage in the text
        span = doc[start:end]

        # get pollutant
        pol = get_pollutant(span)
        # get values
        values = get_values(span)

        # add the matched value to our current article data. If there is already a value stored for the pollutant, we will add it to the list
        if pol not in article_data:
            article_data[pol] = values
        else:
            for value in values:
                if value not in article_data[pol]:
                    article_data[pol].append(value)

        # call the highlight function to highlight the pattern in the text
        highlight_match(span.sent.text)

    def multi_matcher(matcher, doc, i, matches):
        match_id, start, end = matches[i]

        # this is the extracted passage in the text
        span = doc[start:end]

        # get the pollutants and values
        pollutants = get_all_pollutants(span)
        values = get_values(span)

        # ignore if not same amount of pollutants and values
        if len(pollutants) != len(values):
            return

        # print("##############")
        # print(span.sent.text)
        # print(pollutants)
        # print(values)
        # relate each pollutant to a value and add it to our current article data
        for j in range(len(pollutants)):
            current_pollutant = pollutants[j]
            if current_pollutant not in article_data:
                article_data[current_pollutant] = [values[j]]
            elif values[j] not in article_data[current_pollutant]:
                article_data[current_pollutant].append(values[j])

        # call the highlight function to highlight the pattern in the text
        highlight_match(span.sent.text)

    def plus_minus_matcher(matcher, doc, i, matches):
        match_id, start, end = matches[i]

        # this is the extracted passage in the text
        span = doc[start:end]

        # get pollutant
        pollutants = get_all_pollutants(span)
        values = get_plus_minus_values(span)

        for j in range(len(pollutants)):
            current_pollutant = pollutants[j]
            if current_pollutant not in article_data:
                article_data[current_pollutant] = [values[j]]
            elif values[j] not in article_data[current_pollutant]:
                article_data[current_pollutant].append(values[j])

        # call the highlight function to highlight the pattern in the text
        highlight_match(span.sent.text)

    def no_trend_matcher(matcher, doc, i, matches):
        match_id, start, end = matches[i]

        # this is the extracted passage in the text
        span = doc[start:end]

        pollutants = get_all_pollutants(span)
        values = get_no_trend_values(span)
        double = False

        if 2*len(pollutants) == len(values):
            double = True
        for j in range(len(pollutants)):
            current_pollutant = pollutants[j]
            if current_pollutant not in article_data:
                article_data[current_pollutant] = [values[j]]
            elif values[j] not in article_data[current_pollutant]:
                article_data[current_pollutant].append(values[j])
            if double:
                if values[j+len(pollutants)] not in article_data[current_pollutant]:
                    article_data[current_pollutant].append(values[j+len(pollutants)])

        # call the highlight function to highlight the pattern in the text
        highlight_match(span.sent.text)

    def no_pollutant_no_trend(matcher, doc, i, matches):
        match_id, start, end = matches[i]

        # this is the extracted passage in the text
        span = doc[start:end]

        # get the previous sentence to find the pollutant
        prev_sent = ""
        first_token = span[0]
        index = first_token.i
        for k in reversed(range(index)):
            token = doc[k]
            if token.is_sent_end:
                prev_sent = token.sent
                break

        # check if there was a pollutant in the previous sentence
        pols = get_all_pollutants(prev_sent)
        if not pols:
            if type(prev_sent) == str:
                return
            # look at the previous sentence
            first_token = prev_sent[0]
            index = first_token.i
            for k in reversed(range(index)):
                token = doc[k]
                if token.is_sent_end:
                    prev_sent = token.sent
                    break
            pols = get_all_pollutants(prev_sent)
            if not pols:
                return
        pol = pols[-1]
        values = get_no_trend_values(span)
        if pol not in article_data:
            article_data[pol] = values
        else:
            for value in values:
                if value not in article_data[pol]:
                    article_data[pol].append(value)

        # call the highlight function to highlight the pattern in the text
        highlight_match(span.sent.text)

    nlp = spacy.load("en_core_web_sm")
    matcher = Matcher(nlp.vocab)

    # these are the patterns we are looking for
    # NO2 concentrations were reduced by 24%
    pattern = [{"TEXT": {"IN": pollutants_no_number}}, {'TEXT': {"IN": pollutants_numbers}, 'OP': "?"}, {"LEMMA": {"IN": ["average", "mean", "also", "level"]}, "OP": "?"}, {"TEXT": {"IN": ["of", "column"]}, "OP": "?"}, {'LEMMA': {"IN": ["exhibit", "concentration", "emission", "over", "the"]}, 'OP': "?"}, {"TEXT": {"IN": ["entire", "in"]}, "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"TEXT": {"IN": ["interval", "signiﬁcantly", ",", "all", "a"]}, "OP": "?"}, {"LEMMA": {"IN": ["have", "be", "show", "station", "include"]}, "OP": "?"}, {"TEXT": "the", "OP": "?"}, {"TEXT": "prelockdown", "OP": "?"}, {"TEXT": "and", "OP": "?"}, {"TEXT": "lockdown", "OP": "?"}, {"TEXT": "periods", "OP": "?"}, {"TEXT": "(", "OP": "?"}, {"TEXT": "i.e.", "OP": "?"}, {"TEXT": "January", "OP": "?"}, {"TEXT": "–", "OP": "?"}, {"TEXT": "April", "OP": "?"}, {"TEXT": "2020", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"LEMMA": "small", "OP": "?"}, {"LEMMA": {"IN": trend}}, {"TEXT": {"IN": [",", "the", "at", "trend"]}, "OP": "?"}, {"LEMMA": "concentration", "OP": "?"}, {"TEXT": "in", "OP": "?"}, {"TEXT": "2020", "OP": "?"}, {"TEXT": "and", "OP": "?"}, {"TEXT": "its", "OP": "?"}, {"TEXT": "concentration", "OP": "?"}, {"LEMMA": "be", "OP": "?"}, {"LEMMA": {"IN": trend}, "OP": "?"}, {"TEXT": {"IN": ["by", "of", "the"]}, "OP": "?"}, {"TEXT": {"IN": ["approximately", "about", "selected"]}, "OP": "?"}, {"TEXT": "cities", "OP": "?"}, {"LEMMA": "show", "OP": "?"}, {"TEXT": "in", "OP": "?"}, {"TEXT": "Table", "OP": "?"}, {"TEXT": "S1", "OP": "?"}, {"LEMMA": "be", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}]
    long_pattern = [{"TEXT": {"IN": pollutants_no_number}}, {'TEXT': {"IN": pollutants_numbers}, 'OP': "?"}, {"LEMMA": {"IN": ["average", "mean"]}, "OP": "?"}, {'LEMMA': {"IN": ["concentration", "emission"]}, 'OP': "?"}, {"LEMMA": {"IN": ["have", "be", "show"]}, "OP": "?"}, {"LEMMA": "small", "OP": "?"}, {"LEMMA": {"IN": trend}}, {"TEXT": "up", "OP": "?"}, {"TEXT": {"IN": ["by", "of", "to"]}}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": "at", "OP": "?"}, {"TEXT": "the", "OP": "?"}, {"OP": "?"}, {"TEXT": "site", "OP": "?"}, {"TEXT": {"IN": [",", "and"]}}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": "at", "OP": "?"}, {"TEXT": "the", "OP": "?"}, {"OP": "?"}, {"TEXT": "site", "OP": "?"}, {"TEXT": {"IN": [",", "and"]}}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}]
    two_pattern = [{"TEXT": {"IN": pollutants_no_number}}, {'TEXT': {"IN": pollutants_numbers}, 'OP': "?"}, {"LEMMA": {"IN": ["average", "mean"]}, "OP": "?"}, {'LEMMA': {"IN": ["concentration", "emission"]}, 'OP': "?"}, {"LEMMA": {"IN": ["have", "be", "show"]}, "OP": "?"}, {"LEMMA": "small", "OP": "?"}, {"LEMMA": {"IN": trend}}, {"TEXT": {"IN": ["by", "of"]}}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": "and"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}]
    no_pollutant_pattern = [{"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"LEMMA": {"IN": trend}, "OP": "?"}, {"TEXT": "in", "OP": "?"}, {"TEXT": "concentration", "OP": "?"}, {"LEMMA": "be", "OP": "?"}, {"LEMMA": "record", "OP": "?"}, {"TEXT": ","}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": {"IN": ["and", "while"]}, "OP": "?"}, {"TEXT": "a", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"LEMMA": {"IN": trend}}, {"LEMMA": "be", "OP": "?"}, {"LEMMA": "observe", "OP": "?"}, {"TEXT": "at", "OP": "?"}, {"TEXT": "the", "OP": "?"}, {"OP": "?"}, {"TEXT": "site", "OP": "?"}]
    bracket_pattern = [{"LEMMA": "concentration", "OP": "?"}, {"TEXT": "of", "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": "markedly", "OP": "?"}, {"LEMMA": {"IN": trend}, "OP": "?"}, {"TEXT": "("},  {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%", "OP": "?"}, {"TEXT": "and"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%", "OP": "?"}]
    pol_after_number_pattern = [{"TEXT": "lockdown"}, {"TEXT": "emission"}, {"LEMMA": {"IN": trend}}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": "in"}, {"TEXT": {"IN": pollutants_no_number}}]
    # 65% decrease in NO2
    second_basic_pattern = [{"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": "fractional", "OP": "?"}, {"LEMMA": {"IN": trend}}, {"TEXT": {"IN": ["of", "in"]}}, {"TEXT": {"IN": ["surface", "tropospheric"]}, "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}}]
    multi_pattern = [{"LEMMA": {"IN": trend}}, {"TEXT": "of"}, {"TEXT": "~", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": "~", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": "~", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": "and"}, {"TEXT": "~", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": "for"}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": ","}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": ","}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": ","}, {"TEXT": "and"}, {"TEXT": {"IN": pollutants_no_number}}]
    second_multi_pattern = [{"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": "and"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"LEMMA": {"IN": trend}}, {"TEXT": "in"}, {"TEXT": "the"}, {"TEXT": "concentration"}, {"TEXT": "of"}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": ","}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": "and"}, {"TEXT": {"IN": pollutants_no_number}}]
    two_pattern_reverse = [{"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": "and"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"LEMMA": {"IN": trend}}, {"LEMMA": "be"}, {"TEXT": "found"}, {"TEXT": "in"}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": "and"}, {"TEXT": {"IN": pollutants_no_number}}]
    # decreases in NO2 levels in San Francisco and Bakersfield of about 20%
    long_pattern_2 = [{"LEMMA": {"IN": trend}}, {"TEXT": {"IN": ["of", "in"]}}, {"TEXT": "the", "OP": "?"}, {"TEXT": "emission", "OP": "?"}, {"TEXT": "of", "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": "levels", "OP": "?"}, {"TEXT": "in", "OP": "?"}, {"TEXT": "San", "OP": "?"}, {"TEXT": "Francisco", "OP": "?"}, {"TEXT": "and", "OP": "?"}, {"TEXT": "Bakersfield", "OP": "?"}, {"TEXT": {"IN": ["of", "by"]}}, {"TEXT": "about", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": "and", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}]
    # reductions in tropospheric NO2 columns of approximately 40%, 38%, and 20%
    pattern_a = [{"LEMMA": {"IN": trend}}, {"TEXT": "in"}, {"TEXT": "tropospheric", "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": "columns", "OP": "?"}, {"TEXT": "of"}, {"TEXT": "approximately", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": "and"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}]
    # Beijing (31%), Hebei (22%), Shanghai (20%), Shandong (24%), and Hubei (32%), where the NO2 concentrations decrease
    pattern_b = [{"POS": "PROPN"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": ","}, {"POS": "PROPN"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": ","}, {"POS": "PROPN"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": ","}, {"POS": "PROPN"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": ","}, {"POS": "PROPN", "OP": "?"}, {"TEXT": "(", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"TEXT": "(", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"TEXT": "(", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": "and"}, {"POS": "PROPN"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": ","}, {"TEXT": {"IN": ["and", "where"]}}, {"TEXT": {"IN": ["the", "their"]}}, {"TEXT": {"IN": pollutants_no_number}}, {"LEMMA": "concentration", "OP": "?"}, {"LEMMA": {"IN": trend}}]
    # decrease ratio over 20% including Tianjin (20%), Hebei (29%), Shanxi (24%), Shanghai (21%), Jiangsu (31%), Zhejiang (22%), Anhui (30%), Shandong (29%), Henan (33%), Hubei (23%), Shaanxi (22%), and Qinghai (22%)
    pattern_c = [{"LEMMA": {"IN": trend}}, {"TEXT": "ratio", "OP": "?"}, {"TEXT": "over", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": "including"}, {"POS": "PROPN"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": ","}, {"POS": "PROPN"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": ","}, {"POS": "PROPN"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": ","}, {"POS": "PROPN"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": ","}, {"POS": "PROPN"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": ","}, {"POS": "PROPN"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": ","}, {"POS": "PROPN"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": ","}, {"POS": "PROPN"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": ","}, {"POS": "PROPN"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": ","}, {"POS": "PROPN"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": ","}, {"POS": "PROPN"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": ","}, {"TEXT": "and"}, {"POS": "PROPN"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}]
    # decrease of PM2.5 concentration (DR < 5%) is observed in Jiangxi (5%), Guangdong (4%), Guangxi (0%), Chongqing (5%), and
    pattern_d = [{"LEMMA": {"IN": trend}}, {"TEXT": "rate", "OP": "?"}, {"TEXT": "of"}, {"TEXT": {"IN": pollutants_no_number}}, {"LEMMA": "concentration", "OP": "?"}, {"TEXT": {"IN": ["(", "during", "from"]}, "OP": "?"}, {"TEXT": {"IN": ["DR", "COVID-19", "P1"]}, "OP": "?"}, {"TEXT": {"IN": ["<", ",", "to"]}, "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": {"IN": ["%", "and", "P4"]}, "OP": "?"}, {"TEXT": {"IN": [")", "they"]}, "OP": "?"}, {"LEMMA": {"IN": ["be", "which", ","]}, "OP": "?"}, {"LEMMA": {"IN": ["observe", "which"]}, "OP": "?"}, {"LEMMA": {"IN": ["in", "include"]}, "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": ",", "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"TEXT": "(", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"TEXT": "(", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"TEXT": "(", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"TEXT": "(", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"TEXT": "(", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"TEXT": "(", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"TEXT": "(", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": "and", "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"TEXT": "(", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ")", "OP": "?"}]
    # increase of PM10 concentration by 3% and 8%
    pattern_e = [{"LEMMA": {"IN": trend}}, {"TEXT": {"IN": ["in", "of"]}}, {"TEXT": {"IN": pollutants_no_number}}, {"LEMMA": "concentration", "OP": "?"}, {"TEXT": {"IN": ["during", "with"]}, "OP": "?"},{"TEXT": "the", "OP": "?"}, {"TEXT": {"IN": ["lockdown", "a"]}, "OP": "?"}, {"LEMMA": "be", "OP": "?"}, {"LEMMA": {"IN": ["quite", "observe"]}, "OP": "?"}, {"TEXT": {"IN": ["variable", "across"]}, "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": "ranging", "OP": "?"}, {"LEMMA": {"IN": trend}, "OP": "?"}, {"TEXT": "ratio", "OP": "?"}, {"TEXT": {"IN": ["by", "of", "from"]}}, {"TEXT": "about", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": "in", "OP": "?"}, {"TEXT": "the", "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": "to", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": "and", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}]
    # NO2, corresponding to a −71.9%
    pattern_f = [{"TEXT": {"IN": pollutants_no_number}}, {"POS": "NOUN", "OP": "?"}, {"TEXT": {"IN": ["in", ","]}, "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"LEMMA": "show", "OP": "?"}, {"TEXT": "the", "OP": "?"}, {"TEXT": "daily", "OP": "?"}, {"TEXT": "delta", "OP": "?"}, {"LEMMA": {"IN": ["be", "small"]}, "OP": "?"}, {"LEMMA": {"IN": trend}, "OP": "?"}, {"TEXT": {"IN": ["during", ",", "(", "concentration", "and", "for"]}}, {"POS": "PROPN", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": {"IN": ["the", "corresponding", "ACV", "and", "from", "all"]}, "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"TEXT": {"REGEX": "[1-3]?[0-9]{1}"}, "OP": "?"}, {"TEXT": {"IN": ["lockdown", "to", "=", "in", "countries"]}, "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"TEXT": {"REGEX": "[1-3]?[0-9]{1}"}, "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": {"IN": ["ranging", "2020"]}, "OP": "?"}, {"TEXT": {"IN": ["from", "a"]}, "OP": "?"}, {"LEMMA": "be", "OP": "?"}, {"LEMMA": {"IN": trend}, "OP": "?"}, {"TEXT": "by", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ",", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": "(", "OP": "?"}, {"TEXT": "urban", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": "and", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": "(", "OP": "?"}, {"TEXT": "rural", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"TEXT": "for", "OP": "?"}, {"TEXT": "the", "OP": "?"}, {"TEXT": "lowest", "OP": "?"}, {"TEXT": "delta", "OP": "?"}, {"TEXT": "in", "OP": "?"}, {"POS": "PROPN", "OP": "?"}, {"TEXT": "to", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": "(", "OP": "?"}, {"TEXT": "urban", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"TEXT": "and", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}]
    # lowered SO2, NOx, PM2.5 and VOCs emissions by approximately 16–26%, 29–47%, 27–46% and 37–57%
    pattern_g = [{"LEMMA": {"IN": trend}, "OP": "?"}, {"TEXT": "in", "OP": "?"}, {"TEXT": "other", "OP": "?"}, {"TEXT": "pollutants", "OP": "?"}, {"TEXT": "like", "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}, "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}, "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": ",", "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}, "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}, "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": "and"}, {"TEXT": {"IN": pollutants_no_number}}, {"LEMMA": "be", "OP": "?"}, {"POS": "NUM", "OP": "?"}, {"TEXT": "µg", "OP": "?"}, {"TEXT": "m–3", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"POS": "NUM", "OP": "?"}, {"TEXT": "µg", "OP": "?"}, {"TEXT": "m–3", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"POS": "NUM", "OP": "?"}, {"POS": "NOUN", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"POS": "NUM", "OP": "?"}, {"POS": "NOUN", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": "and", "OP": "?"}, {"POS": "NUM", "OP": "?"}, {"POS": "NOUN", "OP": "?"}, {"TEXT": "and", "OP": "?"}, {"TEXT": {"IN": ["concentrations", "emissions"]}, "OP": "?"}, {"TEXT": {"IN": ["show", "signiﬁcantly", "at", "have"]}, "OP": "?"}, {"LEMMA": {"IN": trend}, "OP": "?"}, {"TEXT": {"IN": ["remarkable", "across", "significantly", "the"]}, "OP": "?"}, {"TEXT": {"IN": ["China", "variations", "—", "trafﬁc"]}, "OP": "?"}, {"TEXT": "station", "OP": "?"}, {"LEMMA": {"IN": ["compare", "be"]}, "OP": "?"}, {"TEXT": {"IN": ["with", "respectively", "sharply"]}, "OP": "?"}, {"LEMMA": {"IN": trend}, "OP": "?"}, {"TEXT": {"IN": ["those", "by", "amounting"]}, "OP": "?"}, {"TEXT": {"IN": ["of", "approximately", "about", "to"]}, "OP": "?"}, {"TEXT": "averages", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": "with", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ",", "OP": "?"}, {"TEXT": "and"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ",", "OP": "?"}, {"TEXT": "respectively", "OP": "?"}, {"TEXT": "?", "OP": "?"}, {"LEMMA": {"IN": trend}, "OP": "?"}]
    # PM2.5 and NO2 in northern China have decreased by approximately (29 ± 22%) and (53 ± 10%)
    pattern_h = [{"TEXT": {"IN": pollutants_no_number}}, {"TEXT": "and"}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": "in"}, {"TEXT": "northern"}, {"TEXT": "China"}, {"LEMMA": "have"}, {"LEMMA": {"IN": trend}}, {"TEXT": "by"}, {"TEXT": "approximately", "OP": "?"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "±"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}, {"TEXT": "and"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "±"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ")"}]
    # NO2 reduced by 27.0%, PM2.5 by 10.5%, PM10 by 21.4% and CO by 12.1%.
    pattern_i = [{"TEXT": {"IN": pollutants_no_number}}, {"LEMMA": {"IN": trend}}, {"TEXT": "by"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ",", "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}, "OP": "?"}, {"TEXT": "by", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}, "OP": "?"}, {"TEXT": "by", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": "and", "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}, "OP": "?"}, {"TEXT": "by", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}]
    # decreased by 13.7%, 21.8%, 12.2%, 4.6%, and 46.1% on average for PM2.5, PM10, CO, SO2, and NO2
    pattern_j = [{"LEMMA": {"IN": trend}}, {"TEXT": {"IN": ["of", "by"]}}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": "and", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": {"IN": ["in", "on"]}}, {"TEXT": "the", "OP": "?"}, {"TEXT": "average", "OP": "?"}, {"TEXT": "concentration", "OP": "?"}, {"TEXT": {"IN": ["of", "for"]}}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": "from", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "to", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"POS": {"IN": ["ADP", "PROPN"]}, "OP": "?"}, {"TEXT": "m–3", "OP": "?"}, {"TEXT": ","}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": "from", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "to", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"POS": {"IN": ["ADP", "PROPN"]}, "OP": "?"}, {"TEXT": "m–3", "OP": "?"}, {"TEXT": ","}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": "from", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "to", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"POS": {"IN": ["ADP", "PROPN"]}, "OP": "?"}, {"TEXT": "m–3", "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}, "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": "and"}, {"TEXT": {"IN": pollutants_no_number}}]
    # PM2.5, PM10, SO2, CO, NO2, and O3 concentrations show remarkable variations compared with those of historical averages, with -27%, -36%, -52%, -27%, -40%, and 15% changes during the first month of the lockdown period, and -32%, -30%, -48%, -38%, -29%, and 2%
    pattern_k = [{"TEXT": {"IN": pollutants_no_number}}, {"TEXT": ","}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": ","}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": ","}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": ","}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": ",", "OP": "?"}, {"TEXT": "and"}, {"TEXT": {"IN": pollutants_no_number}},  {"TEXT": "concentrations"}, {"TEXT": "show"}, {"TEXT": "remarkable"}, {"TEXT": "variations"}, {"TEXT": "compared"}, {"TEXT": "with"}, {"TEXT": "those"}, {"TEXT": "of"}, {"TEXT": "historical"}, {"TEXT": "averages"}, {"TEXT": ","}, {"TEXT": "with"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ",", "OP": "?"}, {"TEXT": "and"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": "changes"}, {"TEXT": "during"}, {"TEXT": "the"}, {"TEXT": "first"}, {"TEXT": "month"}, {"TEXT": "of"}, {"TEXT": "the"}, {"TEXT": "lockdown"}, {"TEXT": "period"}, {"TEXT": ","}, {"TEXT": "and"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ","}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": ",", "OP": "?"}, {"TEXT": "and"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}]
    # reduction of 31 μg/m3 (63% reduction)
    pattern_l = [{"LEMMA": {"IN": trend}}, {"LEMMA": "be", "OP": "?"}, {"TEXT": "of"}, {"TEXT": "approximately", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "μg"}, {"TEXT": "/"}, {"TEXT": "m3"}, {"TEXT": "("}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"LEMMA": {"IN": trend}, "OP": "?"}, {"TEXT": ")"}]
    # decrease by 35% for NO2
    pattern_m = [{"LEMMA": {"IN": trend}}, {"TEXT": {"IN": ["of", "by"]}}, {"TEXT": "~", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": "(", "OP": "?"}, {"TEXT": "from", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "to", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"POS": "ADP", "OP": "?"}, {"TEXT": "m–3", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"TEXT": {"IN": ["in", "for"]}}, {"TEXT": {"IN": pollutants_no_number}}]
    # change is −23.5% (urban) and −13.0% (rural)
    pattern_n = [{"TEXT": "change"}, {"LEMMA": "be"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%", "OP": "?"}, {"TEXT": "("}, {"TEXT": "urban"}, {"TEXT": ")"}, {"TEXT": {"IN": ["but", "and"]}}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}]
    # decreased by 42.7% for PM2.5, 47.9% for PM10, 28.6% for SO2, 22.3% for CO and 58.4% for NO2
    pattern_o = [{"LEMMA": {"IN": trend}}, {"TEXT": {"IN": ["of", "by"]}}, {"TEXT": "~", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": "(", "OP": "?"}, {"TEXT": "from", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "to", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"POS": "ADP", "OP": "?"}, {"TEXT": "m–3", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"TEXT": {"IN": ["in", "for"]}}, {"POS": "SPACE", "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": ","}, {"TEXT": "~", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": "(", "OP": "?"}, {"TEXT": "from", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "to", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"POS": "ADP", "OP": "?"}, {"TEXT": "m–3", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"TEXT": {"IN": ["in", "for"]}}, {"POS": "SPACE", "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}}, {"TEXT": ",", "OP": "?"}, {"TEXT": "~", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": "for", "OP": "?"}, {"POS": "SPACE", "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}, "OP": "?"}, {"TEXT": ","}, {"TEXT": "~", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "%", "OP": "?"}, {"TEXT": "for", "OP": "?"}, {"POS": "SPACE", "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}, "OP": "?"}, {"TEXT": ",", "OP": "?"}, {"TEXT": "and", "OP": "?"}, {"TEXT": "~", "OP": "?"}, {"TEXT": {"REGEX": number_regex}}, {"TEXT": "%"}, {"TEXT": "(", "OP": "?"}, {"TEXT": "from", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"TEXT": "to", "OP": "?"}, {"TEXT": {"REGEX": number_regex}, "OP": "?"}, {"POS": {"IN": ["ADP", "PROPN"]}, "OP": "?"}, {"TEXT": "m–3", "OP": "?"}, {"TEXT": ")", "OP": "?"}, {"TEXT": {"IN": ["in", "for"]}}, {"POS": "SPACE", "OP": "?"}, {"TEXT": {"IN": pollutants_no_number}}]

    matcher.add("firstMatcher", [pattern, long_pattern, two_pattern], on_match=basic_pattern_match)
    matcher.add("no_poll_matcher", [no_pollutant_pattern, pattern_c, pattern_l], on_match=no_pollutant_match)
    matcher.add("bracket_matcher", [bracket_pattern, pol_after_number_pattern, second_basic_pattern, pattern_a, pattern_b, long_pattern_2, pattern_d, pattern_e, pattern_f, pattern_m], on_match=bracket_matcher)
    matcher.add("multi_matcher", [multi_pattern, second_multi_pattern, two_pattern_reverse, pattern_g, pattern_i, pattern_j, pattern_o], on_match=multi_matcher)
    matcher.add("plus_minus_matcher", [pattern_h], on_match=plus_minus_matcher)
    matcher.add("long_no_trend_matcher", [pattern_k], on_match=no_trend_matcher)
    matcher.add("no_pollutant_no_trend", [pattern_n], on_match=no_pollutant_no_trend)

    # EASTASIA FOR TABLES and europe, europe2!
    # pattern_f hits "PM2.5, 47.9%", might need to fix

    # this is where we will store all the extracted data
    total_data = []

    # get the files in the directory and iterate over them
    directories = os.listdir(directory)
    directories.sort()
    for file in directories:
        # this is for storing the data of each file
        article_data = {}

        pdf = fitz.open(directory+file)
        link_found = False

        # let's go over page after page
        for pg in range(len(pdf)):
            page = pdf[pg]

            # we need to find the doi, for better evaluation purposes
            if not link_found:
                # checks the links if there is a link to doi.org
                links = page.get_links()
                for link in links:
                    if "uri" in link and "doi.org" in link["uri"]:
                        link_found = True
                        article_data["DOI"] = link["uri"]
                        break

                if not link_found:
                    # or check the lines if there is anything looking like a doi
                    lines = page.get_text().splitlines()
                    for line in lines:
                        line = line.strip()
                        if "doi.org" in line or "doi: " in line.lower():
                            link_found = True
                            line = line.split()
                            for word in line:
                                if "10." in word:
                                    article_data["DOI"] = word
                            break

            # now we need to fit each page into a single line, because PyMuPdf has some problems with newlines and words that are split between lines
            page_as_line = squish_page(page)
            doc = nlp(page_as_line)

            # testing ground

            # for tok in doc:
            #     if tok.text == "Chennai" and tok.nbor().text == "for":
            #         for t in tok.sent:
            #             print(t.text + " -> " + t.pos_ + " -> " + t.dep_ + " -> " + t.lemma_)

            matches = matcher(doc)

        if not link_found:
            print("no link found for " + file)
        else:
            total_data.append(article_data)
        pdf.close()
        # break

    # export the extracted data to a csv file
    df = pd.DataFrame(total_data)
    df.to_csv(r"./extracted_data.csv", index=False)
    print(df)

    # this is for listing which DOI was not found
    not_found = []
    training_data = pd.read_csv("./training_data.csv", sep=";")
    for data in total_data:
        found = False
        for i, doi in training_data["DOI"].iteritems():
            if doi in data["DOI"] or data["DOI"] in doi:
                found = True
                break
        if not found:
            not_found.append(data["DOI"])
    # for data in total_data:
    #     print(data)
    print(not_found)


def squish_page(page):
    """
    This function converts a page into a single line of text
    :param page: the page object that is currently processed
    :return: the text of the page in a single line
    """
    lines = page.get_text().splitlines()
    page_text = ""
    for line in lines:
        line = line.strip()
        if line[-1:] == "-":
            page_text += line[:-1]
        else:
            page_text += line + " "
    return page_text


def get_pollutant(sent):
    """
    This function searches a sentence for a pollutant
    :param sent: the sentence that should be searched
    :return: the pollutant, or an empty string if none was found
    """
    for tok in sent:
        if tok.text in pollutants_no_number:
            return tok.text
    return ""


def get_all_pollutants(sent):
    """
    This function searches a sentence for all occuring pollutants
    :param sent: the sentence that should be searched
    :return: the found pollutants
    """
    pollutants = []
    for tok in sent:
        if tok.text in pollutants_no_number:
            pollutants.append(tok.text)
    return pollutants


def get_values(sent):
    """
    This function searches a sentence for values corresponding to pollutants
    :param sent: the sentence that should be searched
    :return: a list of values for the pollutant
    """
    values = []
    down = True
    for tok in sent:
        # print(tok.text + " --> " + tok.pos_ + " -> " + tok.dep_)
        if tok.lemma_ in negative or tok.text[0] == "-":
            down = True
        elif tok.lemma_ in positive or tok.text[0] == "+":
            down = False
        # add the actual numerical value of the pollutant
        if tok.i + 1 == len(tok.doc):
            break
        if re.search(number_regex, tok.text) and tok.nbor().text == "%":
            # check if the text contains more than just the number
            text = tok.text
            if text[0] in ["−", "+", "~", "-"]:
                text = text[1:]
            if "b" in text:
                text = text.replace("b", "")
            if "e" in text:
                text = text.split("e")[0]
            if "%" in text:
                text = text.split("%")[0]
            if "~" in text:
                text = text.split("~")[0]
            if "–" in text[1:]:
                v = text.split("–")
                try:
                    text = str(round((float(v[0]) + float(v[1]))/2, 2))
                except ValueError:
                    print(v)
                    print("contains not only numbers")
                    print(tok.sent)
                    break
            if "-" in text[1:]:
                v = text.split("-")
                try:
                    text = str(round((float(v[0]) + float(v[1]))/2, 2))
                except ValueError:
                    print(v)
                    print("contains not only numbers")
                    print(tok.sent)
                    break
            if "−" in text[1:]:
                v = text.split("−")
                try:
                    text = str(round((float(v[0]) + float(v[1]))/2, 2))
                except ValueError:
                    print(v)
                    print("contains not only numbers")
                    print(tok.sent)
                    break
            try:
                number = float(text)
            except ValueError:
                print(tok.text + " is no number")
                print(tok.sent)
                break
            current_value = str(number)
            if down:
                current_value = "-" + current_value
            values.append(current_value)

    # we need to convert some negative numbers to positive because sometimes we find the number before the trend
    if not down:
        for j in range(len(values)):
            values[j] = values[j].replace("-", "")
    return values


def get_plus_minus_values(sent):
    values = []
    down = True
    for tok in sent:
        # print(tok.text + " --> " + tok.pos_ + " -> " + tok.dep_)
        if tok.lemma_ in negative or tok.text[0] == "-":
            down = True
        elif tok.lemma_ in positive or tok.text[0] == "+":
            down = False
        # add the actual numerical value of the pollutant
        if re.search(number_regex, tok.text):
            # check if ± is next
            if tok.nbor().text == "±" or tok.nbor().text == "%" and tok.nbor().nbor().text == "±":
                # check if the text contains more than just the number
                text = tok.text
                if text[0] in ["−", "+", "~"]:
                    text = text[1:]
                if "–" in text:
                    v = text.split("–")
                    text = str(round((float(v[0]) + float(v[1]))/2, 2))
                if "-" in text:
                    v = text.split("-")
                    text = str(round((float(v[0]) + float(v[1]))/2, 2))
                if "e" in text:
                    text = text.split("e")[0]
                if "%" in text:
                    text = text.split("%")[0]
                if "~" in text:
                    text = text.split("~")[0]
                number = float(text)
                current_value = str(number)
                if down:
                    current_value = "-" + current_value
                values.append(current_value)

    # we need to convert some negative numbers to positive because sometimes we find the number before the trend
    if not down:
        for j in range(len(values)):
            values[j] = values[j].replace("-", "")
    return values


def get_no_trend_values(sent):
    values = []
    for tok in sent:
        if tok.text not in pollutants_no_number and re.search(number_regex, tok.text):
            try:
                number = float(tok.text)
            except ValueError:
                number = "-" + str(float(tok.text[1:]))
            values.append(str(number))
    return values


if __name__ == "__main__":
    # extract text from the pdf document
    extract_text("./Doc/articles/PDF/")
