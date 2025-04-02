
import csv
from xml.sax import make_parser
from xml.sax.handler import ContentHandler
from collections import Counter
import pandas as pd
import sys

class PadTeller(ContentHandler):
    def __init__(self, filter_wkt=False):
        self.path_stack = []
        self.counter = Counter()
        self.filter_wkt = filter_wkt
        self.inside_ao = False
        self.ao_has_wkt = False
        self.temp_counter = Counter()

    def startElement(self, name, attrs):
        self.path_stack.append(name)
        huidig_pad = "/" + "/".join(self.path_stack)

        if self.filter_wkt:
            if name == 'archeologischOnderzoeksgebied':
                self.inside_ao = True  #! begin van AO-blok
                self.ao_has_wkt = False  #! reset WKT-detectie
                self.temp_counter = Counter()  #! tijdelijke teller voor AO-blok
            elif name == 'WKT' and self.inside_ao:
                self.ao_has_wkt = True  #! markeer dat WKT gevonden is binnen AO-blok

            if self.inside_ao:
                self.temp_counter[huidig_pad] += 1  #! tellen binnen AO-blok
            else:
                self.counter[huidig_pad] += 1  #! tellen buiten AO-blok
        else:
            self.counter[huidig_pad] += 1

    def endElement(self, name):
        if self.filter_wkt and name == 'archeologischOnderzoeksgebied':
            if self.ao_has_wkt:
                self.counter += self.temp_counter  #! voeg alleen toe als WKT aanwezig
            self.inside_ao = False  #! einde van AO-blok
            self.ao_has_wkt = False
            self.temp_counter = Counter()
        self.path_stack.pop()

def tel_paden_in_xml(xml_pad, filter_wkt=False):
    parser = make_parser()
    handler = PadTeller(filter_wkt=filter_wkt)
    parser.setContentHandler(handler)
    parser.parse(xml_pad)
    return handler.counter

def xmls_tellen_naar_df(xml_bestanden, filter_wkt=False):
    totaal = Counter()
    for pad in xml_bestanden:
        print(f"Verwerken: {pad}")
        try:
            totaal += tel_paden_in_xml(pad, filter_wkt=filter_wkt)
        except Exception as e:
            print(f"Fout bij {pad}: {e}")
    df = pd.DataFrame(totaal.items(), columns=["pad", "aantal"])
    df.set_index("pad", inplace=True)
    return df

def vergelijk_tellingen(df_ldv, df_archis):
    alle_paden = df_ldv.index.union(df_archis.index)
    df_ldv_full = df_ldv.reindex(alle_paden, fill_value=0)
    df_archis_full = df_archis.reindex(alle_paden, fill_value=0)
    resultaat = pd.DataFrame({
        "ldv": df_ldv_full["aantal"],
        "archis": df_archis_full["aantal"],
        "verschil_ldv_min_archis": df_ldv_full["aantal"] - df_archis_full["aantal"]
    })
    return resultaat

if __name__ == '__main__':
    filter_flag = '--filter-ao-op-wkt' in sys.argv
    if filter_flag:
        sys.argv.remove('--filter-ao-op-wkt')

    if len(sys.argv) < 4 or '--' not in sys.argv:
        print("Gebruik: python script.py ldv1.xml ldv2.xml -- archis.xml --filter-ao-op-wkt")
        sys.exit(1)

    sep_index = sys.argv.index('--')
    ldv_files = sys.argv[1:sep_index]
    archis_files = sys.argv[sep_index + 1:]

    print("Tellen van paden in ldv-bestanden...")
    df_ldv = xmls_tellen_naar_df(ldv_files)

    print("Tellen van paden in archis-bestanden (volledig)...")
    df_archis_full = xmls_tellen_naar_df(archis_files, filter_wkt=False)

    print("Tellen van paden in archis-bestanden (gefilterd op WKT in AO)...")
    df_archis_filtered = xmls_tellen_naar_df(archis_files, filter_wkt=True)

    print("Vergelijken van resultaten...")
    alle_paden = df_ldv.index.union(df_archis_full.index).union(df_archis_filtered.index)
    df_ldv_full = df_ldv.reindex(alle_paden, fill_value=0)
    df_archis_full = df_archis_full.reindex(alle_paden, fill_value=0)
    df_archis_filtered = df_archis_filtered.reindex(alle_paden, fill_value=0)

    df_result = pd.DataFrame({
        "ldv": df_ldv_full["aantal"],
        "archis": df_archis_full["aantal"],
        "verschil_ldv_min_archis": df_ldv_full["aantal"] - df_archis_full["aantal"],
        "archis_gefilterd": df_archis_filtered["aantal"],
        "verschil_ldv_min_archis_gefilterd": df_ldv_full["aantal"] - df_archis_filtered["aantal"]
    })

    df_result.to_excel("vergelijking_paden_ldv_vs_archis.xlsx")
    print("Resultaat opgeslagen in: vergelijking_paden_ldv_vs_archis.xlsx")
