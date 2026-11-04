package br.diego.i30launcher.nav.gh;

import com.graphhopper.config.Profile;
import com.graphhopper.routing.WeightingFactory;
import com.graphhopper.routing.ev.*;
import com.graphhopper.routing.util.EncodingManager;
import com.graphhopper.routing.weighting.DefaultTurnCostProvider;
import com.graphhopper.routing.weighting.TurnCostProvider;
import com.graphhopper.routing.weighting.Weighting;
import com.graphhopper.routing.weighting.custom.CustomWeighting;
import com.graphhopper.storage.BaseGraph;
import com.graphhopper.util.PMap;
import com.graphhopper.util.Parameters;
import com.graphhopper.util.TurnCostsConfig;

/**
 * Pesagem "car" equivalente ao car.json do GraphHopper (distance_influence 90,
 * priority 0 sem car_access, speed = car_average_speed), escrita à mão para NÃO
 * usar o Janino. No Android o Janino gera bytecode JVM em tempo de execução, que
 * o ART não consegue carregar; por isso o app precisa desta fábrica.
 */
public class CarWeightingFactory implements WeightingFactory {
    private final BaseGraph graph;
    private final EncodingManager em;

    public CarWeightingFactory(BaseGraph graph, EncodingManager em) { this.graph = graph; this.em = em; }

    @Override
    public Weighting createWeighting(Profile profile, PMap requestHints, boolean disableTurnCosts) {
        if (!"car".equals(profile.getName())) throw new IllegalArgumentException("só o perfil car é suportado");
        final BooleanEncodedValue access = em.getBooleanEncodedValue(VehicleAccess.key("car"));
        final DecimalEncodedValue speed = em.getDecimalEncodedValue(VehicleSpeed.key("car"));
        final double maxSpeed = speed.getMaxOrMaxStorableDecimal();
        double heading = requestHints.getDouble(Parameters.Routing.HEADING_PENALTY, Parameters.Routing.DEFAULT_HEADING_PENALTY);
        CustomWeighting.Parameters p = new CustomWeighting.Parameters(
                (e, rev) -> rev ? e.getReverse(speed) : e.get(speed), () -> maxSpeed,
                (e, rev) -> (rev ? e.getReverse(access) : e.get(access)) ? 1.0 : 0.0, () -> 1.0,
                null, 90, heading);
        TurnCostProvider tcp = TurnCostProvider.NO_TURN_COST_PROVIDER;
        if (profile.hasTurnCosts() && !disableTurnCosts) {
            BooleanEncodedValue tr = em.getTurnBooleanEncodedValue(TurnRestriction.key(profile.getName()));
            PMap hints = new PMap(profile.getHints()).putAll(requestHints);
            int uTurn = hints.getInt(Parameters.Routing.U_TURN_COSTS, profile.getTurnCostsConfig().getUTurnCosts());
            tcp = new DefaultTurnCostProvider(tr, graph, new TurnCostsConfig(profile.getTurnCostsConfig()).setUTurnCosts(uTurn), null);
        }
        return new CustomWeighting(tcp, p);
    }
}
