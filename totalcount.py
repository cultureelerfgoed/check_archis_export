

# SAX-handler voor het tellen van elementen in XML. The no-bs parser.
from xml.sax import make_parser
from xml.sax.handler import ContentHandler
from collections import Counter
import pandas as pd
import sys


class ElementCounter(ContentHandler):
    def __init__(self, filter_wkt=False):
        self.counter = Counter()
        self.tag_stack = []
        self.filter_wkt = filter_wkt

        # Voor AO-blok met optionele filtering
        self.inside_archeologisch = False
        self.archeologisch_has_wkt = False
        self.temp_counter = Counter()

    def startElement(self, name, attrs):
        self.tag_stack.append(name)

        if self.filter_wkt and name == 'archeologischOnderzoeksgebied':
            self.inside_archeologisch = True
            self.archeologisch_has_wkt = False
            self.temp_counter = Counter()

        if self.filter_wkt and name == 'WKT' and self.inside_archeologisch:
            self.archeologisch_has_wkt = True

        # Kies of we in tijdelijke buffer of hoofdcounter tellen
        if self.filter_wkt and self.inside_archeologisch:
            target = self.temp_counter
        else:
            target = self.counter

        # Tellen (relaties inbegrepen)
        if name == 'choId':
            if 'isRelatieTot' in self.tag_stack[:-1]:
                target['isRelatieTot:choId'] += 1
            elif 'isRelatieVan' in self.tag_stack[:-1]:
                target['isRelatieVan:choId'] += 1
            else:
                target['choId'] += 1
        else:
            target[name] += 1

    def endElement(self, name):
        if self.filter_wkt and name == 'archeologischOnderzoeksgebied':
            if self.archeologisch_has_wkt:
                self.counter += self.temp_counter

            # Reset AO-context
            self.inside_archeologisch = False
            self.archeologisch_has_wkt = False
            self.temp_counter = Counter()

        self.tag_stack.pop()


def count_elements(xml_file, filter_wkt=False):
    parser = make_parser()
    handler = ElementCounter(filter_wkt=filter_wkt)
    parser.setContentHandler(handler)
    try:
        parser.parse(xml_file)
        return handler.counter
    except Exception:
        print(f"Er is een fout gevonde in bestand {xml_file}")
        return Counter()

def xmls_to_dataframe(xml_paths, filter_wkt=False):
    total_counter = Counter()
    for path in xml_paths:
        print(f"{path} wordt verwerkt")
        total_counter += count_elements(path, filter_wkt=filter_wkt)
    df = pd.DataFrame(total_counter.items(), columns=["element", "count"])
    df.set_index("element", inplace=True)
    return df

def combine_and_compare(df_ldv, df_archis_full, df_archis_filtered):
    all_tags = df_ldv.index.union(df_archis_full.index).union(df_archis_filtered.index)

    df_ldv_full = df_ldv.reindex(all_tags, fill_value=0)
    df_archis_full = df_archis_full.reindex(all_tags, fill_value=0)
    df_archis_filtered_full = df_archis_filtered.reindex(all_tags, fill_value=0)

    result_df = pd.DataFrame({
        "ldv": df_ldv_full["count"],
        "archis": df_archis_full["count"],
        "verschil_ldv_min_archis": df_ldv_full["count"] - df_archis_full["count"],
        "archis_gefilterd": df_archis_filtered_full["count"],
        "verschil_ldv_min_archis_gefilterd": df_ldv_full["count"] - df_archis_filtered_full["count"]
    })

    return result_df

if __name__ == '__main__':
    filter_flag = '--filter-ao-op-wkt' in sys.argv
    if filter_flag:
        sys.argv.remove('--filter-ao-op-wkt')

    if len(sys.argv) < 4 or '--' not in sys.argv:
        print("Gebruik voorbeeld, en let op dat '--filter-ao-op-wkt' optioneel is:\n"
              "python totalcount.py ldv1.xml ldv2.xml -- archis.xml [--filter-ao-op-wkt]")
        sys.exit(1)

    sep_index = sys.argv.index('--')
    ldv_bestanden = sys.argv[1:sep_index]
    archis_bestanden = sys.argv[sep_index + 1:]

    print("Verwerken van ldv data...")
    df_ldv = xmls_to_dataframe(ldv_bestanden)

    print("Verwerken van archis data (volledig)...")
    df_archis_full = xmls_to_dataframe(archis_bestanden, filter_wkt=False)

    print("Verwerken van archis data (gefilterd op WKT in AO)...")
    df_archis_filtered = xmls_to_dataframe(archis_bestanden, filter_wkt=True)

    print("Resultaatvergelijking:")
    result_df = combine_and_compare(df_ldv, df_archis_full, df_archis_filtered)
    print(result_df)

    naam_output = "vergelijking_ldv_vs_archis.xlsx"
    result_df.to_excel(naam_output)
    print(f"Resultaat opgeslagen in: {naam_output}")
