import axios from 'axios'
import express from 'express'

const app = express()
const port = 3000

app.set('view engine', 'ejs')
// app.use(express.json()) // for parsing application/json
app.use(express.urlencoded({ extended: true })) // for parsing application/x-www-form-urlencoded

app.get('/', async (req,res) => {
    try {
    const response = await axios.get('http://127.0.0.1:5000/wallet/balance') // ← hostname di docker
    const { balance } = response.data
    res.render('index', { balance })
  } catch (error) {
    console.error('Error fetching balance:', error.message)
    res.render('index', { balance: null })
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

  res.render('result', { results })
})

app.listen(port, () => {
	console.log(`Example app is listening on http://localhost:${port}`)
})