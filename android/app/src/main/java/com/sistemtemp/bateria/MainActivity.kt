package com.sistemtemp.bateria

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.app.ActivityManager
import android.app.AlertDialog
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothSocket
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ListView
import android.widget.TextView
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID
import java.util.concurrent.Executors

/**
 * Lê as informações do aparelho a cada 5 s, guarda no histórico local e, se conectado,
 * envia ao SistemTemp do PC pela porta serial Bluetooth (SPP): uma linha JSON por leitura.
 */
class MainActivity : Activity() {
    private val spp = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
    private val intervaloMs = 5000L
    private val maxHistorico = 200

    // fundo, card, borda, texto, texto secundário: as mesmas cores do app do PC
    private val corFundo = Color.parseColor("#0B1120")
    private val corCard = Color.parseColor("#111827")
    private val corBorda = Color.parseColor("#1F2937")
    private val corTexto = Color.parseColor("#E2E8F0")
    private val corCinza = Color.parseColor("#94A3B8")

    private val bluetooth = Executors.newSingleThreadExecutor()
    private val relogio = Handler(Looper.getMainLooper())
    private val historico = ArrayList<String>()
    private val arquivoHistorico by lazy { File(filesDir, "historico.txt") }

    private lateinit var lblAparelho: TextView
    private lateinit var lblTemp: TextView
    private lateinit var lblDetalhes: TextView
    private lateinit var lblStatus: TextView
    private lateinit var botao: Button
    private lateinit var listaAdapter: ArrayAdapter<String>

    @Volatile private var socket: BluetoothSocket? = null
    @Volatile private var conectado = false
    @Volatile private var conectando = false

    private val tique = object : Runnable {
        override fun run() {
            registrarLeitura()
            relogio.postDelayed(this, intervaloMs)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // shortcut: só lê/envia com o app aberto (tela ligada); para segundo plano, mover para um Foreground Service
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.statusBarColor = corFundo
        montarTela()
        carregarHistorico()
        temPermissao()
        relogio.post(tique)
    }

    override fun onDestroy() {
        relogio.removeCallbacks(tique)
        desconectar(null)
        bluetooth.shutdownNow()
        super.onDestroy()
    }

    // ---------- tela ----------

    private fun Int.dp() = (this * resources.displayMetrics.density).toInt()

    private fun card() = GradientDrawable().apply {
        setColor(corCard)
        setStroke(1.dp(), corBorda)
        cornerRadius = 12.dp().toFloat()
    }

    private fun texto(tamanho: Float, cor: Int, negrito: Boolean = false) = TextView(this).apply {
        textSize = tamanho
        setTextColor(cor)
        if (negrito) typeface = Typeface.DEFAULT_BOLD
    }

    private fun montarTela() {
        val logo = ImageView(this).apply { setImageResource(R.drawable.ic_logo) }
        lblAparelho = texto(13f, corCinza).apply { text = nomeDoCelular() }
        val cabecalho = LinearLayout(this).apply {
            gravity = Gravity.CENTER_VERTICAL
            addView(logo, LinearLayout.LayoutParams(44.dp(), 44.dp()))
            addView(LinearLayout(this@MainActivity).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(12.dp(), 0, 0, 0)
                addView(texto(22f, Color.WHITE, true).apply { text = "SistemTemp" })
                addView(lblAparelho)
            })
        }

        lblTemp = texto(34f, Color.WHITE, true).apply { text = "-- °C" }
        lblDetalhes = texto(15f, corTexto).apply { text = "Lendo a bateria…" }
        val cardAtual = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = card()
            setPadding(16.dp(), 12.dp(), 16.dp(), 14.dp())
            addView(texto(12f, corCinza, true).apply { text = "🌡  TEMPERATURA DA BATERIA" })
            addView(lblTemp)
            addView(lblDetalhes)
        }

        botao = Button(this).apply {
            text = "Conectar ao PC"
            setTextColor(Color.WHITE)
            isAllCaps = false
            textSize = 16f
            background = GradientDrawable().apply {
                setColor(Color.parseColor("#EF4444"))
                cornerRadius = 8.dp().toFloat()
            }
            setOnClickListener { if (conectado || conectando) desconectar("Desconectado") else escolherPc() }
        }
        val btnLimpar = ImageButton(this).apply {
            setImageResource(android.R.drawable.ic_menu_delete)
            contentDescription = "Excluir histórico"
            background = card()
            setOnClickListener { confirmarLimparHistorico() }
        }
        val linhaBotoes = LinearLayout(this).apply {
            addView(botao, LinearLayout.LayoutParams(0, 48.dp(), 1f))
            addView(btnLimpar, LinearLayout.LayoutParams(48.dp(), 48.dp()).apply { leftMargin = 8.dp() })
        }
        lblStatus = texto(14f, Color.parseColor("#64748B")).apply {
            text = "● Desconectado do PC"
            setPadding(0, 10.dp(), 0, 0)
        }

        listaAdapter = object : ArrayAdapter<String>(this, android.R.layout.simple_list_item_1, historico) {
            override fun getView(position: Int, convertView: View?, parent: ViewGroup): View =
                (super.getView(position, convertView, parent) as TextView).apply {
                    setTextColor(corTexto)
                    textSize = 13f
                    typeface = Typeface.MONOSPACE
                }
        }
        val lista = ListView(this).apply {
            adapter = listaAdapter
            background = card()
            divider = GradientDrawable().apply { setColor(corBorda) }
            dividerHeight = 1
        }

        setContentView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(corFundo)
            setPadding(20.dp(), 28.dp(), 20.dp(), 20.dp())
            addView(cabecalho)
            addView(cardAtual, margemTopo(18))
            addView(linhaBotoes, margemTopo(14))
            addView(lblStatus)
            addView(texto(13f, corCinza, true).apply { text = "HISTÓRICO DE LEITURAS" }, margemTopo(18))
            addView(lista, LinearLayout.LayoutParams(-1, 0, 1f).apply { topMargin = 8.dp() })
        })
    }

    private fun margemTopo(dp: Int) = LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp.dp() }

    private fun status(texto: String, cor: String) = runOnUiThread {
        lblStatus.text = "● $texto"
        lblStatus.setTextColor(Color.parseColor(cor))
    }

    // ---------- leituras ----------

    private fun registrarLeitura() {
        val l = coletar() ?: return
        val nivel = if (l.has("nivel")) "${l.getInt("nivel")} %" else "--"
        val raio = if (l.getBoolean("carregando")) " ⚡" else ""
        lblTemp.text = String.format(Locale.US, "%.1f °C", l.getDouble("temp"))
        lblDetalhes.text = String.format(
            Locale.US, "🔋 %s%s   ·   %.2f V   ·   RAM %d %%\nSaúde: %s   ·   Android %s",
            nivel, raio, l.getDouble("tensao"), l.getInt("ram"), l.getString("saude"), l.getString("android"),
        )

        val hora = SimpleDateFormat("dd/MM HH:mm:ss", Locale.US).format(Date())
        historico.add(0, String.format(Locale.US, "%s  %5.1f °C  %5s%s  %.2f V", hora, l.getDouble("temp"), nivel, raio, l.getDouble("tensao")))
        while (historico.size > maxHistorico) historico.removeAt(historico.size - 1)
        listaAdapter.notifyDataSetChanged()
        runCatching { arquivoHistorico.writeText(historico.joinToString("\n")) }

        if (conectado) bluetooth.execute {
            try {
                socket?.outputStream?.write((l.toString() + "\n").toByteArray())
            } catch (e: Exception) {
                desconectar("Conexão com o PC caiu")
            }
        }
    }

    private fun carregarHistorico() {
        runCatching { historico.addAll(arquivoHistorico.readLines().filter { it.isNotBlank() }.take(maxHistorico)) }
        listaAdapter.notifyDataSetChanged()
    }

    private fun confirmarLimparHistorico() {
        AlertDialog.Builder(this)
            .setTitle("Excluir histórico?")
            .setMessage("Todas as leituras salvas neste celular serão apagadas.")
            .setPositiveButton("Excluir") { _, _ ->
                historico.clear()
                listaAdapter.notifyDataSetChanged()
                runCatching { arquivoHistorico.delete() }
            }
            .setNegativeButton("Cancelar", null)
            .show()
    }

    /** Informações do aparelho agora; null se o Android não informar a temperatura da bateria. */
    private fun coletar(): JSONObject? {
        val bateria = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED)) ?: return null
        val decimos = bateria.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Int.MIN_VALUE)
        if (decimos == Int.MIN_VALUE) return null

        val nivel = bateria.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
        val escala = bateria.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
        val estado = bateria.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
        val memoria = ActivityManager.MemoryInfo().also { (getSystemService(ACTIVITY_SERVICE) as ActivityManager).getMemoryInfo(it) }

        return JSONObject().apply {
            put("temp", decimos / 10.0)
            if (nivel >= 0 && escala > 0) put("nivel", nivel * 100 / escala)
            put("tensao", bateria.getIntExtra(BatteryManager.EXTRA_VOLTAGE, 0) / 1000.0)
            put("carregando", estado == BatteryManager.BATTERY_STATUS_CHARGING || estado == BatteryManager.BATTERY_STATUS_FULL)
            put("saude", saude(bateria.getIntExtra(BatteryManager.EXTRA_HEALTH, -1)))
            put("ram", (100 - memoria.availMem * 100 / memoria.totalMem).toInt())
            put("nome", nomeDoCelular())
            put("modelo", "${Build.MANUFACTURER} ${Build.MODEL}")
            put("android", Build.VERSION.RELEASE)
        }
    }

    private fun saude(codigo: Int) = when (codigo) {
        BatteryManager.BATTERY_HEALTH_GOOD -> "Boa"
        BatteryManager.BATTERY_HEALTH_OVERHEAT -> "Superaquecida"
        BatteryManager.BATTERY_HEALTH_DEAD -> "Morta"
        BatteryManager.BATTERY_HEALTH_OVER_VOLTAGE -> "Sobretensão"
        BatteryManager.BATTERY_HEALTH_COLD -> "Fria"
        else -> "Desconhecida"
    }

    /** Nome que o usuário deu ao aparelho (ex.: "Galaxy do Samuel"), ou fabricante + modelo. */
    private fun nomeDoCelular(): String =
        (Settings.Global.getString(contentResolver, "device_name") ?: "${Build.MANUFACTURER} ${Build.MODEL}").trim()

    // ---------- bluetooth ----------

    private fun temPermissao(): Boolean {
        if (Build.VERSION.SDK_INT < 31) return true
        if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED) return true
        requestPermissions(arrayOf(Manifest.permission.BLUETOOTH_CONNECT), 1)
        return false
    }

    @SuppressLint("MissingPermission")
    private fun escolherPc() {
        if (!temPermissao()) return
        val adapter = (getSystemService(BLUETOOTH_SERVICE) as BluetoothManager).adapter
        if (adapter == null || !adapter.isEnabled) {
            status("Ligue o Bluetooth do celular", "#F59E0B")
            return
        }
        val pareados = adapter.bondedDevices.toList()
        if (pareados.isEmpty()) {
            status("Nenhum aparelho pareado: pareie o PC no Bluetooth", "#F59E0B")
            return
        }
        AlertDialog.Builder(this)
            .setTitle("Escolha o PC")
            .setItems(pareados.map { it.name ?: it.address }.toTypedArray()) { _, i -> conectar(pareados[i]) }
            .show()
    }

    @SuppressLint("MissingPermission")
    private fun conectar(pc: BluetoothDevice) {
        conectando = true
        botao.text = "Cancelar"
        status("Conectando a ${pc.name}…", "#F59E0B")
        bluetooth.execute {
            try {
                val s = pc.createRfcommSocketToServiceRecord(spp)
                socket = s
                s.connect()
                conectado = true
                conectando = false
                status("Conectado: ${pc.name}", "#10B981")
                runOnUiThread { botao.text = "Desconectar" }
            } catch (e: Exception) {
                if (conectando) desconectar("Falhou: abra a porta COM de Entrada no SistemTemp do PC antes")
            }
        }
    }

    /** texto null = só fecha (app saindo). */
    private fun desconectar(texto: String?) {
        conectado = false
        conectando = false
        runCatching { socket?.close() }
        socket = null
        if (texto == null) return
        status(texto, if (texto == "Desconectado") "#64748B" else "#EF4444")
        runOnUiThread { botao.text = "Conectar ao PC" }
    }
}
