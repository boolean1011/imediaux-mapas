package br.diego.mapas;

import br.diego.i30launcher.nav.gh.CarProfile;
import br.diego.i30launcher.nav.gh.CarWeightingFactory;
import com.graphhopper.GraphHopper;
import com.graphhopper.GraphHopperConfig;
import com.graphhopper.config.CHProfile;
import com.graphhopper.routing.WeightingFactory;

import com.graphhopper.GHRequest;
import com.graphhopper.GHResponse;

import java.util.List;

/**
 * Uso: Importer &lt;arquivo.osm.pbf&gt; &lt;pastaDoGrafo&gt;
 * Mesma configuração de GraphHopperProvider.config (app), só que importando em RAM.
 * Perfil "car" com restrições de conversão + CH.
 */
public final class Importer {
    public static void main(String[] a) {
        if (a.length == 4 && a[0].equals("verificar")) { verificar(a[1], a[2], a[3]); return; }
        if (a.length != 2) { System.err.println("uso: Importer <pbf> <pasta> | verificar <pasta> lat,lon lat,lon"); System.exit(2); }
        GraphHopper h = new GraphHopper() {
            @Override protected WeightingFactory createWeightingFactory() {
                return new CarWeightingFactory(getBaseGraph().getBaseGraph(), getEncodingManager());
            }
        };
        GraphHopperConfig c = new GraphHopperConfig();
        c.putObject("graph.location", a[1]);
        c.putObject("datareader.file", a[0]);
        c.putObject("graph.encoded_values", "car_access, car_average_speed");
        c.putObject("graph.dataaccess.default_type", "RAM_STORE");
        c.putObject("graph.sort", true);
        c.putObject("import.osm.ignored_highways",
                "footway,cycleway,path,pedestrian,steps,bridleway,construction,proposed,platform,corridor,elevator,track");
        c.putObject("prepare.min_network_size", 200);
        c.setProfiles(List.of(CarProfile.profile(true)));
        c.setCHProfiles(List.of(new CHProfile("car")));
        long t0 = System.nanoTime();
        h.init(c);
        h.importOrLoad();
        System.out.printf("OK %s nos=%d arestas=%d em %.1f s%n", a[1], h.getBaseGraph().getNodes(),
                h.getBaseGraph().getEdges(), (System.nanoTime() - t0) / 1e9);
        h.close();
    }

    /** Abre o grafo como o app abre (MMAP_RO, só leitura) e calcula uma rota de teste. */
    static void verificar(String dir, String de, String para) {
        GraphHopper h = new GraphHopper() {
            @Override protected WeightingFactory createWeightingFactory() {
                return new CarWeightingFactory(getBaseGraph().getBaseGraph(), getEncodingManager());
            }
        };
        GraphHopperConfig c = new GraphHopperConfig();
        c.putObject("graph.location", dir);
        c.putObject("graph.encoded_values", "car_access, car_average_speed");
        c.putObject("graph.dataaccess.default_type", "MMAP_RO");
        c.putObject("import.osm.ignored_highways",
                "footway,cycleway,path,pedestrian,steps,bridleway,construction,proposed,platform,corridor,elevator,track");
        c.setProfiles(List.of(CarProfile.profile(true)));
        c.setCHProfiles(List.of(new CHProfile("car")));
        h.init(c);
        h.setAllowWrites(false);
        if (!h.load()) throw new IllegalStateException("grafo não carregou: " + dir);
        String[] x = de.split(","), y = para.split(",");
        GHResponse r = h.route(new GHRequest(Double.parseDouble(x[0]), Double.parseDouble(x[1]),
                Double.parseDouble(y[0]), Double.parseDouble(y[1])).setProfile("car"));
        if (r.hasErrors()) throw new IllegalStateException(r.getErrors().toString());
        System.out.printf("ROTA OK %.1f km %.0f min%n", r.getBest().getDistance() / 1000, r.getBest().getTime() / 60000.0);
        h.close();
    }
}
