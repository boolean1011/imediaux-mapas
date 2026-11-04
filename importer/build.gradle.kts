// Importador dos grafos offline. CarProfile/CarWeightingFactory são CÓPIAS dos arquivos do app
// (app/src/main/java/br/diego/i30launcher/nav/gh) — precisam ficar idênticos para o grafo bater com o app.
plugins { java; application }
repositories { mavenCentral() }
java { toolchain { languageVersion.set(JavaLanguageVersion.of(17)) } }
dependencies {
    implementation("com.graphhopper:graphhopper-core:11.1") { exclude(group = "ch.qos.logback") }
    implementation("org.slf4j:slf4j-simple:2.0.17")
}
application { mainClass.set("br.diego.mapas.Importer") }
