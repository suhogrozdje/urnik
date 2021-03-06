from django.core.cache import cache
from django.http import QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.views.decorators.http import require_POST
from .models import *


def izbrani_semester(request):
    urejanje = request.session.get('urejanje', False)
    kljuc_semestra = 'semester_za_urejanje' if urejanje else 'semester_za_ogled'
    semester = cache.get(kljuc_semestra)
    if not semester:
        if urejanje:
            semester = Semester.objects.latest('od')
        else:
            semester = Semester.objects.filter(objavljen=True).latest('od')
        cache.set(kljuc_semestra, semester, None)
    return semester

def zacetna_stran(request):
    ucilnice = Ucilnica.objects.objavljene()
    return render(request, 'zacetna_stran.html', {
        'stolpci_smeri': [
            Letnik.objects.filter(oddelek=Letnik.MATEMATIKA),
            Letnik.objects.filter(oddelek=Letnik.FIZIKA),
        ],
        'ucilnice': ucilnice,
    })


def kombiniran_pogled_form(request):
    osebe = sorted(Oseba.objects.aktivni(), key=lambda oseba: oseba.vrstni_red())
    columns = 3
    length = len(osebe)
    per_column = length // columns
    ucilnice = Ucilnica.objects.objavljene()
    return render(request, 'kombiniran_pogled.html', {
        'stolpci_smeri': [
            Letnik.objects.filter(oddelek=Letnik.MATEMATIKA),
            Letnik.objects.filter(oddelek=Letnik.FIZIKA),
        ],
        'osebe': [osebe[i*per_column:(i+1)*per_column] for i in range(columns)],
        'ucilnice': ucilnice,
        'naslov': 'Kombiniran pogled',
    })


def rezervacije(request):
    rezervacije = []
    queryset = Rezervacija.objects.prihajajoce().prefetch_related(
        'ucilnice',
        'osebe',
        'ucilnice__srecanja__ucitelji',
        'ucilnice__srecanja__predmet',
    )
    for rezervacija in queryset:
        for ucilnica in rezervacija.ucilnice.all():
            rezervacije.append({
                'ucilnica': ucilnica,
                'osebe': rezervacija.osebe,
                'od': rezervacija.od,
                'do': rezervacija.do,
                'opomba': rezervacija.opomba,
                'dan': rezervacija.dan,
                'teden': rezervacija.teden(),
            })
    rezervacije.sort(key=lambda r: (r['dan'], r['ucilnica'].oznaka, r['od']))
    return render(request, 'rezervacije.html', {
        'naslov': 'Rezervacije učilnic',
        'rezervacije': rezervacije,
    })


def urnik(request, srecanja, naslov, barve=None):
    legenda = barve
    if barve is None:
        barve = Predmet.objects.filter(srecanja__in=srecanja).distinct()
    if request.user.is_authenticated and request.session.get('urejanje', False):
        if request.META['QUERY_STRING']:
            next_url = '{}?{}'.format(request.path, request.META['QUERY_STRING'])
        else:
            next_url = request.path
        return render(request, 'urnik.html', {
            'nacin': 'urejanje',
            'naslov': naslov,
            'srecanja': srecanja.urnik(barve=barve),
            'odlozena_srecanja': izbrani_semester(request).srecanja.odlozena(),
            'prekrivanja_po_tipih': izbrani_semester(request).srecanja.prekrivanja(),
            'next': next_url,
            'barve': barve,
        })
    else:
        return render(request, 'urnik.html', {
            'nacin': 'ogled',
            'naslov': naslov,
            'srecanja': srecanja.urnik(barve=barve),
            'barve': legenda,
        })


def urnik_osebe(request, oseba_id):
    oseba = get_object_or_404(Oseba, id=oseba_id)
    naslov = str(oseba)
    return urnik(request, oseba.vsa_srecanja(izbrani_semester(request)), naslov)


def urnik_letnika(request, letnik_id):
    letnik = get_object_or_404(Letnik, id=letnik_id)
    naslov = str(letnik)
    return urnik(request, letnik.srecanja(izbrani_semester(request)).all(), naslov)


def urnik_ucilnice(request, ucilnica_id):
    ucilnica = get_object_or_404(Ucilnica, id=ucilnica_id)
    naslov = 'Učilnica {}'.format(ucilnica.oznaka)
    return urnik(request, ucilnica.srecanja.filter(semester=izbrani_semester(request)), naslov, barve=[])


def urnik_predmeta(request, predmet_id):
    predmet = get_object_or_404(Predmet, id=predmet_id)
    naslov = str(predmet)
    return urnik(request, predmet.srecanja.filter(semester=izbrani_semester(request)), naslov)


def kombiniran_pogled(request):
    letniki = Letnik.objects.filter(id__in=request.GET.getlist('letnik'))
    osebe = Oseba.objects.filter(id__in=request.GET.getlist('oseba'))
    ucilnice = Ucilnica.objects.filter(id__in=request.GET.getlist('ucilnica'))
    srecanja_letnikov = izbrani_semester(request).srecanja.filter(predmet__letniki__in=letniki)
    srecanja_uciteljev = izbrani_semester(request).srecanja.filter(ucitelji__in=osebe)
    srecanja_slusateljev = izbrani_semester(request).srecanja.filter(predmet__slusatelji__in=osebe)
    srecanja_ucilnic = izbrani_semester(request).srecanja.filter(ucilnica__in=ucilnice)
    srecanja = (srecanja_letnikov | srecanja_uciteljev |
                srecanja_slusateljev | srecanja_ucilnic).distinct()
    return urnik(request, srecanja, 'Kombiniran pogled', barve=list(letniki) + list(osebe) + list(ucilnice))


def proste_ucilnice(request):
    teden = request.GET.get('teden', None)
    try:
        teden = parse_date(teden)
        weekday = teden.weekday()
        if weekday <= 5:
            teden -= datetime.timedelta(days=weekday)
        else:
            teden += datetime.timedelta(days=7-weekday)
    except:
        teden = None

    pokazi_zasedene = bool(request.GET.get('pz', False))

    ucilnice = request.GET.getlist('ucilnica')
    if ucilnice:
        ucilnice = Ucilnica.objects.objavljene().filter(pk__in=ucilnice)
        if not ucilnice.exists():
            ucilnice = Ucilnica.objects.objavljene()
    else:
        ucilnice = Ucilnica.objects.objavljene()

    tip = set(request.GET.getlist('tip'))
    tip &= set(Ucilnica.OBJAVLJENI_TIPI)
    if not tip: tip = set(Ucilnica.OBJAVLJENI_TIPI)

    velikost = set(request.GET.getlist('velikost'))
    velikost &= {v[0] for v in UcilnicaQuerySet.VELIKOST}
    if not velikost: velikost = None

    proste = ProsteUcilnice(ucilnice, tip, velikost)
    if teden:
        proste.upostevaj_rezervacije(teden)
        # teh semestrov bi moralo biti 0 ali 1
        prekrivajoci_semestri = Semester.objects.filter(od__lte=teden,do__gte=teden)
        for semester in prekrivajoci_semestri:
            proste.dodaj_srecanja_semestra(semester)
    else:
        proste.dodaj_srecanja_semestra(izbrani_semester(request))

    termini = proste.dobi_termine()
    for t in termini:
        t.filtriraj_ucilnice(pokazi_zasedene=pokazi_zasedene)

    return render(request, 'proste_ucilnice.html', {
        'naslov': 'Proste učilnice',
        'termini': termini,

        # get parameters
        'pokazi_zasedene': pokazi_zasedene,
        'velikosti': velikost,
        'tipi': [] if tip == set(Ucilnica.OBJAVLJENI_TIPI) else tip,
        'teden': teden,

        # possible values
        'mozne_velikosti_ucilnic': UcilnicaQuerySet.VELIKOST,
        'mozni_tipi_ucilnic': [u for u in Ucilnica.TIP if u[0] in Ucilnica.OBJAVLJENI_TIPI],
        'mozni_tedni': sorted(set(r.teden() for r in Rezervacija.objects.prihajajoce())),
        'ustrezne_ucilnice': list(ucilnice),
    })


@require_POST
def proste_ucilnice_filter(request):
    tipi = [k for k in Ucilnica.OBJAVLJENI_TIPI if request.POST.get(k, '') == 'on']
    velikosti = [k for k, v in UcilnicaQuerySet.VELIKOST if request.POST.get(k, '') == 'on']
    q = QueryDict(request.POST.get('qstring', ''), mutable=True)
    q.setlist('tip', tipi)
    q.setlist('velikost', velikosti)
    response = redirect('proste')
    response['Location'] += "?" + q.urlencode()
    return response


@login_required
def premakni_srecanje(request, srecanje_id):
    srecanje = get_object_or_404(Srecanje, id=srecanje_id)
    if request.method == 'POST':
        dan = int(request.POST['dan'])
        ura = int(request.POST['ura'])
        ucilnica = get_object_or_404(Ucilnica, id=request.POST['ucilnica'])
        srecanje.premakni(dan, ura, ucilnica)
        return redirect(request.POST['next'])
    else:
        return render(request, 'urnik.html', {
            'nacin': 'premikanje',
            'naslov': 'Premikanje srečanja',
            'srecanja': srecanje.povezana_srecanja().urnik(),
            'odlozena_srecanja': izbrani_semester(request).srecanja.odlozena(),
            'prekrivanja_po_tipih': {},
            'prosti_termini': srecanje.prosti_termini(request.GET['tip'], 'MAT' if 'matematika' in ','.join(
                group.name for group in request.user.groups.all()) else 'FIZ'),
            'premaknjeno_srecanje': srecanje,
            'next': request.META.get('HTTP_REFERER', reverse('zacetna_stran')),
        })


@login_required
def podvoji_srecanje(request, srecanje_id):
    srecanje = get_object_or_404(Srecanje, id=srecanje_id)
    srecanje.podvoji()
    return redirect(request.META.get('HTTP_REFERER', reverse('zacetna_stran')))


@login_required
def odlozi_srecanje(request, srecanje_id):
    srecanje = get_object_or_404(Srecanje, id=srecanje_id)
    srecanje.odlozi()
    return redirect(request.META.get('HTTP_REFERER', reverse('zacetna_stran')))


@login_required
def nastavi_trajanje_srecanja(request, srecanje_id):
    srecanje = get_object_or_404(Srecanje, id=srecanje_id)
    trajanje = int(request.POST['trajanje'])
    srecanje.nastavi_trajanje(trajanje)
    return redirect(request.META.get('HTTP_REFERER', reverse('zacetna_stran')))


@login_required
def preklopi_urejanje(request):
    request.session['urejanje'] = not request.session.get('urejanje', False)
    return redirect(request.META.get('HTTP_REFERER', reverse('zacetna_stran')))


def bug_report(request):
    return render(request, 'bugreport.html', {
        'naslov': 'Prijavi napako',
    })


def help_page(request):
    return render(request, 'help.html', {
        'naslov': 'Navodila in pomoč',
    })


def print_all(request):
    return render(request, 'print_all.html', {
        'naslov': 'Množično tiskanje',
        'oddelki': Letnik.ODDELEK,
        'moznosti': [('printall_ucilnice', 'učilnice'), ('printall_smeri', 'smeri')],
    })


def print_all_ucilnice(request, oddelek):
    return render(request, 'print_all_list.html', {
        'links': [reverse('urnik_ucilnice', args=[u.id]) for u in Ucilnica.objects.filter(tip=oddelek)]
    })


def print_all_smeri(request, oddelek):
    return render(request, 'print_all_list.html', {
        'links': [reverse('urnik_letnika', args=[l.id]) for l in Letnik.objects.filter(oddelek=oddelek)]
    })
