import axios from 'axios'
import express from 'express'

const app = express()
const port = 3000

app.set('view engine', 'ejs')
// app.use(express.json()) // for parsing application/json
app.use(express.urlencoded({ extended: true })) // for parsing application/x-www-form-urlencoded

app.get('/', async (req,res) => {
    try {
    const response = await axios.get('http://127.0.0.1:5000/wallet/balance')
    const { address,balance } = response.data
    // const address = "octCfT6N3yqRnCGjqAmNQ3NW7wC19N9ny3HwP91Pnm3eweJ"
    // const balance = 90.41
    res.render('index', { address,balance })
  } catch (error) {
    console.error('Error fetching balance:', error.message)
    res.render('index', { address: null, balance: null })
  }
})

app.post('/multisend', async (req, res) => {
  const { amount, addresses } = req.body
  const list = addresses.split('\n').map(a => a.trim()).filter(Boolean)

  const { nonce: baseNonce } = (await axios.get('http://127.0.0.1:5000/wallet/balance')).data
  let currentNonce = baseNonce

  let results = []
  for (const to of list) {
    try {
      const response = await axios.post('http://127.0.0.1:5000/wallet/send', {
        to,
        amount,
        message: 'multisend',
        nonce: currentNonce
      })
      currentNonce++
      results.push({ to, success: true, hash: response.data.tx_hash })
    } catch (err) {
      results.push({ to, success: false, error: err.response?.data?.error || err.message })
    }
  }
  // let results = [
  //   {
  //     to: "octCfT6N3yqRnCGjqAmNQ3NW7wC19N9ny3HwP91Pnm3eweJ",
  //     success: true,
  //     hash: "2ba806e9491b97de71bf12c5fc3805eba62dcaac7ad52fcb493f1a5017b4d48c"
  //   },
  //   {
  //     to: "octCfT6N3yqRnCGjqAmNQ3NW7wC19N9ny3HwP91Pnm3eweJ",
  //     success: false,
  //     hash: "2ba806e9491b97de71bf12c5fc3805eba62dcaac7ad52fcb493f1a5017b4d48c"
  //   },
  //   {
  //     to: "octCfT6N3yqRnCGjqAmNQ3NW7wC19N9ny3HwP91Pnm3eweJ",
  //     success: true,
  //     hash: "2ba806e9491b97de71bf12c5fc3805eba62dcaac7ad52fcb493f1a5017b4d48c"
  //   },
  // ]

  res.render('result', { results })
})

app.listen(port, () => {
	console.log(`Example app is listening on http://localhost:${port}`)
})